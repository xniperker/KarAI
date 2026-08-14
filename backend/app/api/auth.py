from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.db.session import get_db
from app.db.models import User
from app.db.schemas import UserRegister, UserLogin, Token, UserOut
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserOut, status_code=201)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    email_str = user_in.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email_str))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    hashed_pwd = get_password_hash(user_in.password)
    new_user = User(
        email=email_str,
        password_hash=hashed_pwd,
        role=user_in.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login(
    form_data: Optional[OAuth2PasswordRequestForm] = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # Support form_data from Swagger UI as well as default credentials
    email_str = form_data.username.strip().lower() if form_data else "test@karai.io"
    password_str = form_data.password if form_data else "1234"
    
    result = await db.execute(select(User).where(User.email == email_str))
    user = result.scalars().first()
    
    # Auto-register test user if logging in with test/1234 for the first time
    if not user and (email_str in ["test", "test@karai.io"]):
        hashed_pwd = get_password_hash(password_str)
        user = User(
            email=email_str,
            password_hash=hashed_pwd,
            role="sme_user"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user or not verify_password(password_str, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    
    token = create_access_token(subject=user.id, role=user.role)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        user_id=user.id,
        email=user.email,
        role=user.role
    )

@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
