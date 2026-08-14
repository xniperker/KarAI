import pandas as pd
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction, ComplianceCheck, Violation
from app.db.schemas import ComplianceCheckOut
from app.api.auth import get_current_user
from app.services.compliance import ComplianceValidator

router = APIRouter(prefix="/compliance", tags=["GST Compliance"])

@router.post("/check", response_model=ComplianceCheckOut)
async def run_compliance_check(
    dataset_id: str,
    filing_period: str = "2025-Q1",
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
        raise HTTPException(status_code=400, detail="Dataset has no transactions.")
        
    # Map to DataFrame
    txn_dicts = []
    txn_map = {}
    for t in txns:
        txn_map[t.transaction_id] = t.id
        txn_dicts.append({
            "transaction_id": t.transaction_id,
            "txn_date": t.txn_date,
            "amount": t.amount,
            "party_name": t.party_name,
            "gstin": t.gstin,
            "category": t.category,
            "invoice_number": t.invoice_number
        })
    df_txns = pd.DataFrame(txn_dicts)
    
    # Run Compliance Engine
    score, violations_list, counts = ComplianceValidator.validate_dataset(df_txns, filing_period=filing_period)
    
    # Create ComplianceCheck record
    cc = ComplianceCheck(
        dataset_id=dataset_id,
        filing_period=filing_period,
        compliance_score=score,
        total_violations=counts["total_violations"],
        critical_count=counts["critical_count"],
        major_count=counts["major_count"],
        minor_count=counts["minor_count"]
    )
    db.add(cc)
    await db.commit()
    await db.refresh(cc)
    
    # Create Violation records
    v_objs = []
    for v in violations_list:
        orig_txn_id = v.get("transaction_id")
        db_txn_id = txn_map.get(orig_txn_id)
        v_obj = Violation(
            compliance_check_id=cc.id,
            transaction_id=db_txn_id,
            violation_type=v["violation_type"],
            severity=v["severity"],
            description=v["description"],
            remediation=v["remediation"]
        )
        v_objs.append(v_obj)
        
    db.add_all(v_objs)
    await db.commit()
    
    # Return reloaded check with violations
    res_final = await db.execute(
        select(ComplianceCheck)
        .options(selectinload(ComplianceCheck.violations))
        .where(ComplianceCheck.id == cc.id)
    )
    return res_final.scalars().first()

@router.get("/dataset/{dataset_id}/summary")
async def get_compliance_summary_by_dataset(
    dataset_id: str,
    severity: Optional[str] = None,
    page: int = 1,
    limit: int = 15,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch latest compliance check for dataset
    cc_res = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.dataset_id == dataset_id)
        .order_by(ComplianceCheck.checked_at.desc())
    )
    cc = cc_res.scalars().first()
    if not cc:
        return {
            "compliance_score": 100.0,
            "total_violations": 0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "rule_summaries": [],
            "items": [],
            "total": 0,
            "page": page,
            "pages": 0
        }

    # Aggregate violations count per Rule Code across entire dataset
    rule_agg_query = (
        select(
            Violation.violation_type,
            Violation.severity,
            func.count(Violation.id).label("affected_txns"),
            Violation.description,
            Violation.remediation
        )
        .where(Violation.compliance_check_id == cc.id)
        .group_by(Violation.violation_type, Violation.severity)
    )
    rule_res = await db.execute(rule_agg_query)
    rule_rows = rule_res.all()

    rule_summaries = []
    for r in rule_rows:
        rule_summaries.append({
            "rule_code": r[0],
            "severity": r[1],
            "affected_count": r[2],
            "sample_description": r[3],
            "remediation": r[4]
        })

    # Detailed Violations Query
    v_query = (
        select(Violation)
        .join(Transaction, isouter=True)
        .options(selectinload(Violation.transaction))
        .where(Violation.compliance_check_id == cc.id)
    )

    if severity and severity != "all":
        v_query = v_query.where(Violation.severity == severity)

    # Count total matching
    count_query = select(func.count()).select_from(v_query.subquery())
    total_res = await db.execute(count_query)
    total_matching = total_res.scalar() or 0

    offset = (page - 1) * limit
    v_query = v_query.offset(offset).limit(limit)
    v_res = await db.execute(v_query)
    violations = v_res.scalars().all()

    items = []
    for v in violations:
        txn_info = None
        if v.transaction:
            txn_info = {
                "txn_id": v.transaction.transaction_id,
                "amount": v.transaction.amount,
                "party_name": v.transaction.party_name,
                "gstin": v.transaction.gstin
            }
        items.append({
            "id": v.id,
            "rule_code": v.violation_type,
            "severity": v.severity,
            "description": v.description,
            "remediation": v.remediation,
            "transaction": txn_info
        })

    import math
    pages = math.ceil(total_matching / limit) if total_matching > 0 else 0

    return {
        "compliance_score": cc.compliance_score,
        "total_violations": cc.total_violations,
        "critical_count": cc.critical_count,
        "major_count": cc.major_count,
        "minor_count": cc.minor_count,
        "rule_summaries": rule_summaries,
        "items": items,
        "total": total_matching,
        "page": page,
        "limit": limit,
        "pages": pages
    }
