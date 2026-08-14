import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import pandas as pd
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction, ModelRun, AnomalyResult, ComplianceCheck, Violation, Report
from app.db.schemas import ReportOut
from app.api.auth import get_current_user
from app.services.reports import ReportGenerator

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.post("/generate", response_model=ReportOut)
async def generate_audit_report(
    dataset_id: str,
    report_type: str = "pdf",  # pdf or excel
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch dataset
    ds_res = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id))
    dataset = ds_res.scalars().first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    # Fetch transactions
    txns_res = await db.execute(select(Transaction).where(Transaction.dataset_id == dataset_id))
    txns = txns_res.scalars().all()
    
    # Fetch compliance check
    cc_res = await db.execute(
        select(ComplianceCheck)
        .options(selectinload(ComplianceCheck.violations))
        .where(ComplianceCheck.dataset_id == dataset_id)
        .order_by(ComplianceCheck.checked_at.desc())
    )
    cc = cc_res.scalars().first()
    comp_score = cc.compliance_score if cc else 100.0
    violations_list = []
    if cc and cc.violations:
        for v in cc.violations:
            violations_list.append({
                "transaction_id": v.transaction_id or "N/A",
                "violation_type": v.violation_type,
                "severity": v.severity,
                "description": v.description,
                "remediation": v.remediation
            })

    # Fetch latest anomaly results
    mr_res = await db.execute(
        select(ModelRun)
        .where(ModelRun.dataset_id == dataset_id, ModelRun.status == "completed")
        .order_by(ModelRun.run_timestamp.desc())
    )
    mr = mr_res.scalars().first()
    anomalies_list = []
    anom_results_list = []
    if mr:
        ar_res = await db.execute(
            select(AnomalyResult)
            .options(selectinload(AnomalyResult.transaction))
            .where(AnomalyResult.model_run_id == mr.id)
            .order_by(AnomalyResult.anomaly_score.desc())
        )
        anom_results = ar_res.scalars().all()
        for idx, a in enumerate(anom_results):
            anom_results_list.append({
                "index": idx,
                "anomaly_score": a.anomaly_score,
                "risk_category": a.risk_category
            })
            if a.transaction and a.risk_category in ["suspicious", "high_risk", "critical"]:
                anomalies_list.append({
                    "transaction_id": a.transaction.transaction_id,
                    "amount": a.transaction.amount,
                    "party_name": a.transaction.party_name,
                    "anomaly_score": a.anomaly_score,
                    "risk_category": a.risk_category
                })

    # Create dummy report record ID
    import uuid
    report_id = str(uuid.uuid4())
    filing_period = dataset.filing_period or "2025-Q1"

    if report_type.lower() == "excel":
        df_txns = pd.DataFrame([{
            "transaction_id": t.transaction_id,
            "txn_date": t.txn_date,
            "amount": t.amount,
            "party_name": t.party_name,
            "gstin": t.gstin,
            "category": t.category,
            "invoice_number": t.invoice_number
        } for t in txns])
        file_path = ReportGenerator.generate_excel_report(report_id, df_txns, anom_results_list, violations_list)
    else:
        file_path = ReportGenerator.generate_pdf_report(
            report_id=report_id,
            dataset_name=dataset.filename,
            filing_period=filing_period,
            compliance_score=comp_score,
            total_txns=len(txns),
            flagged_count=len(anomalies_list),
            violations=violations_list,
            anomalies=anomalies_list
        )

    # Save Report Record to DB
    report_rec = Report(
        id=report_id,
        user_id=current_user.id,
        dataset_id=dataset_id,
        report_type=report_type.lower(),
        file_path=file_path,
        status="ready"
    )
    db.add(report_rec)
    await db.commit()
    await db.refresh(report_rec)
    
    return report_rec

@router.get("", response_model=List[ReportOut])
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Report).where(Report.user_id == current_user.id).order_by(Report.generated_at.desc()))
    return result.scalars().all()

@router.get("/{report_id}/download")
async def download_report_file(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Report).where(Report.id == report_id, Report.user_id == current_user.id))
    report = res.scalars().first()
    if not report or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file not found.")
        
    media_type = "application/pdf" if report.report_type == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(
        report.file_path,
        filename=os.path.basename(report.file_path),
        media_type=media_type
    )
