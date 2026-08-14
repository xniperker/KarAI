import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
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

@router.get("/{check_id}", response_model=ComplianceCheckOut)
async def get_compliance_check(
    check_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(ComplianceCheck)
        .options(selectinload(ComplianceCheck.violations))
        .where(ComplianceCheck.id == check_id)
    )
    cc = res.scalars().first()
    if not cc:
        raise HTTPException(status_code=404, detail="Compliance check not found.")
    return cc
