import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt, JWTError
from cryptography.fernet import Fernet
import base64
import hashlib
from app.core.config import settings

def get_fernet_key() -> bytes:
    key_hash = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)

fernet = Fernet(get_fernet_key())

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as e:
        return False

def get_password_hash(password: str) -> str:
    pw_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode('utf-8')

def create_access_token(subject: Union[str, Any], role: str = "sme_user", expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def encrypt_sensitive_data(data: str) -> str:
    if not data:
        return ""
    return fernet.encrypt(data.encode()).decode()

def decrypt_sensitive_data(token: str) -> str:
    if not token:
        return ""
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        return token
