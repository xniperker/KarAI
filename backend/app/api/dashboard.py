from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction, ModelRun, AnomalyResult, ComplianceCheck, Violation
from app.db.schemas import DashboardSummary
from app.api.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    dataset_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Determine target dataset
    if not dataset_id:
        ds_res = await db.execute(
            select(Dataset)
            .where(Dataset.user_id == current_user.id)
            .order_by(Dataset.upload_date.desc())
        )
        latest_ds = ds_res.scalars().first()
        if not latest_ds:
            return DashboardSummary(
                total_transactions=0,
                flagged_count=0,
                compliance_score=100.0,
                overall_risk_level="Low",
                risk_distribution={"normal": 0, "suspicious": 0, "high_risk": 0, "critical": 0},
                top_anomalies=[],
                recent_violations=[]
            )
        dataset_id = latest_ds.id

    # Total Transactions
    t_count_res = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.dataset_id == dataset_id)
    )
    total_txns = t_count_res.scalar() or 0

    # Latest Compliance Check
    cc_res = await db.execute(
        select(ComplianceCheck)
        .options(selectinload(ComplianceCheck.violations))
        .where(ComplianceCheck.dataset_id == dataset_id)
        .order_by(ComplianceCheck.checked_at.desc())
    )
    latest_cc = cc_res.scalars().first()
    comp_score = latest_cc.compliance_score if latest_cc else 100.0
    violations_list = []
    if latest_cc and latest_cc.violations:
        for v in latest_cc.violations[:5]:
            violations_list.append({
                "rule": v.violation_type,
                "severity": v.severity,
                "description": v.description,
                "remediation": v.remediation
            })

    # Latest Model Run Anomaly Results
    mr_res = await db.execute(
        select(ModelRun)
        .where(ModelRun.dataset_id == dataset_id, ModelRun.status == "completed")
        .order_by(ModelRun.run_timestamp.desc())
    )
    latest_mr = mr_res.scalars().first()

    risk_dist = {"normal": 0, "suspicious": 0, "high_risk": 0, "critical": 0}
    flagged_count = 0
    top_anomalies = []

    if latest_mr:
        anom_res = await db.execute(
            select(AnomalyResult)
            .options(selectinload(AnomalyResult.transaction))
            .where(AnomalyResult.model_run_id == latest_mr.id)
            .order_by(AnomalyResult.anomaly_score.desc())
        )
        anomalies = anom_res.scalars().all()
        for a in anomalies:
            cat = a.risk_category
            risk_dist[cat] = risk_dist.get(cat, 0) + 1
            if cat in ["suspicious", "high_risk", "critical"]:
                flagged_count += 1
                
        for a in anomalies[:6]:
            if a.transaction:
                top_anomalies.append({
                    "id": a.id,
                    "txn_id": a.transaction.transaction_id,
                    "amount": a.transaction.amount,
                    "party_name": a.transaction.party_name,
                    "gstin": a.transaction.gstin,
                    "score": a.anomaly_score,
                    "risk": a.risk_category,
                    "shap_values": a.shap_values or {}
                })

    # Determine Overall Risk Level
    crit = risk_dist.get("critical", 0)
    high = risk_dist.get("high_risk", 0)
    if crit > 5 or comp_score < 60:
        overall_risk = "Critical"
    elif crit > 0 or high > 10 or comp_score < 80:
        overall_risk = "High"
    elif high > 0 or risk_dist.get("suspicious", 0) > 15:
        overall_risk = "Medium"
    else:
        overall_risk = "Low"

    return DashboardSummary(
        total_transactions=total_txns,
        flagged_count=flagged_count,
        compliance_score=comp_score,
        overall_risk_level=overall_risk,
        risk_distribution=risk_dist,
        top_anomalies=top_anomalies,
        recent_violations=violations_list
    )

@router.get("/scatter")
async def get_scatter_data(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mr_res = await db.execute(
        select(ModelRun)
        .where(ModelRun.dataset_id == dataset_id, ModelRun.status == "completed")
        .order_by(ModelRun.run_timestamp.desc())
    )
    latest_mr = mr_res.scalars().first()
    if not latest_mr:
        return []

    anom_res = await db.execute(
        select(AnomalyResult)
        .options(selectinload(AnomalyResult.transaction))
        .where(AnomalyResult.model_run_id == latest_mr.id)
    )
    anomalies = anom_res.scalars().all()

    scatter_points = []
    for a in anomalies:
        if a.transaction:
            scatter_points.append({
                "txn_id": a.transaction.transaction_id,
                "amount": a.transaction.amount,
                "score": a.anomaly_score,
                "risk": a.risk_category,
                "party": a.transaction.party_name
            })
    return scatter_points
