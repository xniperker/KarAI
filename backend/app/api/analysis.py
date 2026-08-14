import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction, ModelRun, AnomalyResult
from app.db.schemas import ModelRunOut, AnomalyResultOut
from app.api.auth import get_current_user
from app.ml.engine import AnomalyEngine

router = APIRouter(prefix="/analysis", tags=["ML Analysis"])

@router.post("/run", response_model=ModelRunOut)
async def run_anomaly_detection(
    dataset_id: str,
    contamination: float = 0.05,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch dataset
    res_ds = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id))
    dataset = res_ds.scalars().first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
        
    # Fetch transactions
    res_txns = await db.execute(select(Transaction).where(Transaction.dataset_id == dataset_id))
    txns = res_txns.scalars().all()
    if not txns:
        raise HTTPException(status_code=400, detail="Dataset has no transactions to analyze.")
        
    # Convert transactions to DataFrame for ML engine
    txn_dicts = []
    for t in txns:
        txn_dicts.append({
            "id": t.id,
            "transaction_id": t.transaction_id,
            "txn_date": t.txn_date,
            "amount": t.amount,
            "party_name": t.party_name,
            "gstin": t.gstin,
            "category": t.category,
            "invoice_number": t.invoice_number
        })
    df_txns = pd.DataFrame(txn_dicts)
    
    # Create ModelRun entry
    model_run = ModelRun(
        dataset_id=dataset_id,
        model_name="IsolationForest",
        model_version="v1.0.0",
        parameters={"contamination": contamination, "n_estimators": 200},
        status="running"
    )
    db.add(model_run)
    await db.commit()
    await db.refresh(model_run)
    
    # Execute ML Detection + SHAP
    ml_results, metrics = AnomalyEngine.run_detection(df_txns, contamination=contamination)
    
    # Save AnomalyResults to DB
    anomaly_objs = []
    for r in ml_results:
        idx = r["index"]
        target_txn_id = txns[idx].id
        anom_obj = AnomalyResult(
            transaction_id=target_txn_id,
            model_run_id=model_run.id,
            anomaly_score=r["anomaly_score"],
            risk_category=r["risk_category"],
            shap_values=r["shap_values"]
        )
        anomaly_objs.append(anom_obj)
        
    db.add_all(anomaly_objs)
    
    # Update ModelRun status and metrics
    model_run.status = "completed"
    model_run.metrics = metrics
    await db.commit()
    await db.refresh(model_run)
    
    return model_run

@router.get("/runs/{run_id}", response_model=ModelRunOut)
async def get_model_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ModelRun).where(ModelRun.id == run_id))
    mr = result.scalars().first()
    if not mr:
        raise HTTPException(status_code=404, detail="Model run not found.")
    return mr

@router.get("/dataset/{dataset_id}/latest-results")
async def get_dataset_latest_results(
    dataset_id: str,
    risk_category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mr_res = await db.execute(
        select(ModelRun)
        .where(ModelRun.dataset_id == dataset_id, ModelRun.status == "completed")
        .order_by(ModelRun.run_timestamp.desc())
    )
    mr = mr_res.scalars().first()
    if not mr:
        return {"items": [], "total": 0, "page": page, "pages": 0}

    query = (
        select(AnomalyResult)
        .join(Transaction)
        .options(selectinload(AnomalyResult.transaction))
        .where(AnomalyResult.model_run_id == mr.id)
    )

    if risk_category and risk_category != "all":
        query = query.where(AnomalyResult.risk_category == risk_category)

    if search:
        search_fmt = f"%{search}%"
        query = query.where(
            (Transaction.transaction_id.ilike(search_fmt)) |
            (Transaction.party_name.ilike(search_fmt)) |
            (Transaction.gstin.ilike(search_fmt)) |
            (Transaction.category.ilike(search_fmt))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * limit
    query = query.order_by(AnomalyResult.anomaly_score.desc()).offset(offset).limit(limit)
    res = await db.execute(query)
    anomalies = res.scalars().all()

    items = []
    for a in anomalies:
        if a.transaction:
            items.append({
                "id": a.id,
                "txn_id": a.transaction.transaction_id,
                "txn_date": a.transaction.txn_date,
                "amount": a.transaction.amount,
                "party_name": a.transaction.party_name,
                "gstin": a.transaction.gstin,
                "category": a.transaction.category,
                "invoice_number": a.transaction.invoice_number,
                "score": a.anomaly_score,
                "risk": a.risk_category,
                "shap_values": a.shap_values or {}
            })

    import math
    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }
