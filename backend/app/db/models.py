import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="sme_user", nullable=False)  # admin, consultant, sme_user
    is_active = Column(Boolean, default=True, nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Dataset(Base):
    __tablename__ = "datasets"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    row_count = Column(Integer, default=0, nullable=False)
    file_hash = Column(String(64), nullable=False)
    status = Column(String(20), default="ready", nullable=False)  # pending, processing, ready, error
    filing_period = Column(String(20), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="datasets")
    transactions = relationship("Transaction", back_populates="dataset", cascade="all, delete-orphan")
    model_runs = relationship("ModelRun", back_populates="dataset", cascade="all, delete-orphan")
    compliance_checks = relationship("ComplianceCheck", back_populates="dataset", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="dataset", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(String(100), nullable=False)
    txn_date = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    party_name = Column(String(255), nullable=False)
    gstin = Column(String(20), nullable=True)
    category = Column(String(100), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    raw_data = Column(JSON, nullable=True)
    
    dataset = relationship("Dataset", back_populates="transactions")
    anomaly_results = relationship("AnomalyResult", back_populates="transaction", cascade="all, delete-orphan")
    violations = relationship("Violation", back_populates="transaction")


class ModelRun(Base):
    __tablename__ = "model_runs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(50), default="IsolationForest", nullable=False)
    model_version = Column(String(20), default="v1.0.0", nullable=False)
    parameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    status = Column(String(20), default="completed", nullable=False)
    run_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    
    dataset = relationship("Dataset", back_populates="model_runs")
    anomaly_results = relationship("AnomalyResult", back_populates="model_run", cascade="all, delete-orphan")


class AnomalyResult(Base):
    __tablename__ = "anomaly_results"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    transaction_id = Column(String(36), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    model_run_id = Column(String(36), ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False)
    anomaly_score = Column(Float, nullable=False)  # 0.0000 - 1.0000
    risk_category = Column(String(20), nullable=False)  # normal, suspicious, high_risk, critical
    shap_values = Column(JSON, nullable=True)
    is_confirmed_anomaly = Column(Boolean, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    transaction = relationship("Transaction", back_populates="anomaly_results")
    model_run = relationship("ModelRun", back_populates="anomaly_results")


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    filing_period = Column(String(20), nullable=False)
    compliance_score = Column(Float, default=100.0, nullable=False)  # 0 - 100
    total_violations = Column(Integer, default=0, nullable=False)
    critical_count = Column(Integer, default=0, nullable=False)
    major_count = Column(Integer, default=0, nullable=False)
    minor_count = Column(Integer, default=0, nullable=False)
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    dataset = relationship("Dataset", back_populates="compliance_checks")
    violations = relationship("Violation", back_populates="compliance_check", cascade="all, delete-orphan")


class Violation(Base):
    __tablename__ = "violations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    compliance_check_id = Column(String(36), ForeignKey("compliance_checks.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=True)
    violation_type = Column(String(100), nullable=False)  # RULE-001, RULE-002, etc.
    severity = Column(String(20), nullable=False)  # critical, major, minor
    description = Column(Text, nullable=False)
    remediation = Column(Text, nullable=False)
    
    compliance_check = relationship("ComplianceCheck", back_populates="violations")
    transaction = relationship("Transaction", back_populates="violations")


class Report(Base):
    __tablename__ = "reports"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(10), nullable=False)  # pdf, excel
    file_path = Column(String(500), nullable=False)
    status = Column(String(20), default="ready", nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="reports")
    dataset = relationship("Dataset", back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="audit_logs")
