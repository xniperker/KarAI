import os
import hashlib
import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction
from app.db.schemas import DatasetOut, TransactionOut
from app.api.auth import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/datasets", tags=["Datasets"])

@router.post("/upload", response_model=DatasetOut)
async def upload_csv_dataset(
    file: UploadFile = File(...),
    filing_period: Optional[str] = Form("2025-Q1"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()
    
    # Save file locally
    saved_filename = f"{file_hash[:12]}_{file.filename}"
    file_path = os.path.join(settings.DATASETS_DIR, saved_filename)
    with open(file_path, "wb") as f:
        f.write(contents)
        
    # Read CSV using pandas
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {str(e)}")
        
    # Validate required columns
    required_cols = {"amount", "party_name", "txn_date"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing mandatory columns: {list(missing)}")
        
    row_count = len(df)
    
    # Create Dataset record
    dataset_rec = Dataset(
        user_id=current_user.id,
        filename=file.filename,
        row_count=row_count,
        file_hash=file_hash,
        status="ready",
        filing_period=filing_period
    )
    db.add(dataset_rec)
    await db.commit()
    await db.refresh(dataset_rec)
    
    # Batch insert Transactions
    transaction_objs = []
    for idx, row in df.iterrows():
        txn_id = str(row.get("transaction_id", f"TXN-{idx+1:05d}"))
        txn_obj = Transaction(
            dataset_id=dataset_rec.id,
            transaction_id=txn_id,
            txn_date=str(row.get("txn_date", "")),
            amount=float(row.get("amount", 0.0)),
            party_name=str(row.get("party_name", "")),
            gstin=str(row.get("gstin", "")) if pd.notna(row.get("gstin")) else None,
            category=str(row.get("category", "")) if pd.notna(row.get("category")) else None,
            invoice_number=str(row.get("invoice_number", "")) if pd.notna(row.get("invoice_number")) else None,
            raw_data=row.to_dict()
        )
        transaction_objs.append(txn_obj)
        
    db.add_all(transaction_objs)
    await db.commit()
    
    return dataset_rec

@router.get("", response_model=List[DatasetOut])
async def list_user_datasets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Dataset).where(Dataset.user_id == current_user.id).order_by(Dataset.upload_date.desc()))
    return result.scalars().all()

@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset_by_id(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id))
    ds = result.scalars().first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return ds

@router.get("/{dataset_id}/transactions", response_model=List[TransactionOut])
async def get_dataset_transactions(
    dataset_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.dataset_id == dataset_id)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
