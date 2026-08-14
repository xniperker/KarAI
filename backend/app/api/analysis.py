import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
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

@router.get("/runs/{run_id}/results", response_model=List[AnomalyResultOut])
async def get_model_run_results(
    run_id: str,
    risk_category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(AnomalyResult)
        .options(selectinload(AnomalyResult.transaction))
        .where(AnomalyResult.model_run_id == run_id)
    )
    if risk_category:
        query = query.where(AnomalyResult.risk_category == risk_category)
        
    query = query.order_by(AnomalyResult.anomaly_score.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
