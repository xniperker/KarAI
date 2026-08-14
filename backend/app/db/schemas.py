from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

# Auth Schemas
class UserRegister(BaseModel):
    email: str
    password: str = Field(..., min_length=1)  # Flexible length for simple testing (e.g. 1234)
    role: str = "sme_user"  # admin, consultant, sme_user

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    role: str

class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Dataset Schemas
class DatasetOut(BaseModel):
    id: str
    user_id: str
    filename: str
    row_count: int
    file_hash: str
    status: str
    filing_period: Optional[str] = None
    upload_date: datetime
    
    class Config:
        from_attributes = True

# Transaction Schema
class TransactionOut(BaseModel):
    id: str
    transaction_id: str
    txn_date: str
    amount: float
    party_name: str
    gstin: Optional[str] = None
    category: Optional[str] = None
    invoice_number: Optional[str] = None
    
    class Config:
        from_attributes = True

# Anomaly Results Schemas
class AnomalyResultOut(BaseModel):
    id: str
    transaction_id: str
    transaction: Optional[TransactionOut] = None
    anomaly_score: float
    risk_category: str
    shap_values: Optional[Dict[str, float]] = None
    is_confirmed_anomaly: Optional[bool] = None
    reviewer_notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class ModelRunOut(BaseModel):
    id: str
    dataset_id: str
    model_name: str
    model_version: str
    status: str
    run_timestamp: datetime
    completed_at: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# GST Compliance Schemas
class ViolationOut(BaseModel):
    id: str
    violation_type: str
    severity: str
    description: str
    remediation: str
    transaction_id: Optional[str] = None
    
    class Config:
        from_attributes = True

class ComplianceCheckOut(BaseModel):
    id: str
    dataset_id: str
    filing_period: str
    compliance_score: float
    total_violations: int
    critical_count: int
    major_count: int
    minor_count: int
    checked_at: datetime
    violations: List[ViolationOut] = []
    
    class Config:
        from_attributes = True

# Dashboard Summary Schema
class DashboardSummary(BaseModel):
    total_transactions: int
    flagged_count: int
    compliance_score: float
    overall_risk_level: str
    risk_distribution: Dict[str, int]
    top_anomalies: List[Dict[str, Any]]
    recent_violations: List[Dict[str, Any]]

# Report Schemas
class ReportOut(BaseModel):
    id: str
    user_id: str
    dataset_id: str
    report_type: str
    status: str
    generated_at: datetime
    download_url: Optional[str] = None
    
    class Config:
        from_attributes = True
