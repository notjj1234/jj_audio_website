"""JWT auth, password hashing, and FastAPI dependencies."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import settings
from backend import db as db_module
from backend.db import get_db
from backend.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
REFRESH_COOKIE = "att_refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": user_id, "email": email, "type": "access", "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return jwt.encode(
        {"sub": user_id, "type": "refresh", "exp": expire, "jti": secrets.token_hex(8)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def ensure_bootstrap_admin() -> User:
    db = db_module.SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.bootstrap_admin_email).first()
        if existing:
            db.expunge(existing)
            return existing
        user = User(
            id=str(uuid.uuid4()),
            email=settings.bootstrap_admin_email,
            password_hash=hash_password(settings.bootstrap_admin_password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def _extract_bearer(request: Request, creds: HTTPAuthorizationCredentials | None) -> str | None:
    if creds and creds.credentials:
        return creds.credentials
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


async def get_current_user_optional(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    token = _extract_bearer(request, creds)
    if not token:
        # WebSocket / query fallback
        token = request.query_params.get("access_token")
    if not token:
        return None
    payload = decode_token(token, "access")
    return get_user_by_id(db, payload["sub"])


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if user:
        return user
    if not settings.require_auth:
        admin = ensure_bootstrap_admin()
        # Re-attach in current session
        attached = get_user_by_id(db, admin.id)
        if attached:
            return attached
        return admin
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def sign_artifact_token(job_id: str, kind: str, user_id: str) -> str:
    exp = int(
        (datetime.now(timezone.utc) + timedelta(seconds=settings.artifact_sign_ttl_sec)).timestamp()
    )
    msg = f"{job_id}:{kind}:{user_id}:{exp}"
    sig = hmac.new(settings.secret_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_artifact_token(job_id: str, kind: str, user_id: str, token: str) -> bool:
    try:
        exp_s, sig = token.split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(datetime.now(timezone.utc).timestamp()):
        return False
    msg = f"{job_id}:{kind}:{user_id}:{exp}"
    expected = hmac.new(settings.secret_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
