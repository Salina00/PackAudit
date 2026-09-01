import re
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import UserCreate, UserLogin, UserResponse, AuthTokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def validate_password_strength(password: str) -> None:
    """
    Validates password strength:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special symbol
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter (A-Z)."
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter (a-z)."
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one digit (0-9)."
        )
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one special character (@, #, $, %, etc.)."
        )

def hash_password(password: str, salt: str = None) -> str:
    """
    Hashes password with SHA-256 and salt.
    """
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies plain password against hashed password with salt.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 2:
            return False
        salt, expected_hash = parts
        computed_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False

@router.post("/signup", response_model=AuthTokenResponse)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new consumer user account.
    """
    email_clean = payload.email.strip().lower()
    
    # 1. Email format check
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email_clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )
        
    # 2. Check if email already registered
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists. Please sign in."
        )
        
    # 3. Password Strength Validation
    validate_password_strength(payload.password)
    
    # 4. Create user
    hashed_pwd = hash_password(payload.password)
    user = User(
        email=email_clean,
        full_name=payload.full_name.strip() or "Consumer",
        hashed_password=hashed_pwd,
        role="consumer"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = secrets.token_urlsafe(32)
    
    return {
        "user": user,
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=AuthTokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates an existing consumer user.
    """
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials."
        )
        
    token = secrets.token_urlsafe(32)
    
    return {
        "user": user,
        "access_token": token,
        "token_type": "bearer"
    }
