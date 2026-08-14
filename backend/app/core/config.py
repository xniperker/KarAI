import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "KarAI — Automated Tax Compliance & Anomaly Detection"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    JWT_SECRET_KEY: str = "super_secret_karai_jwt_key_32_bytes_long_hash_string_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    ENCRYPTION_KEY: str = "gZ8rF_V2L2_5QZ530v-tW0M-V_u0W0M-V_u0W0M-V_u="  # Sample Fernet key for dev
    
    # Database - Default to local zero-config Async SQLite, overridable via env to Postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./karai.db"
    
    # Storage
    REPORTS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports_storage")
    DATASETS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datasets_storage")
    
    # Default ML sensitivity threshold
    DEFAULT_CONTAMINATION: float = 0.05
    
    class Config:
        case_sensitive = True

settings = Settings()

os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs(settings.DATASETS_DIR, exist_ok=True)
