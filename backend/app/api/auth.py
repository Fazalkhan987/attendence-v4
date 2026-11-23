from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import ChangePassword, LoginRequest, TokenResponse, UserOut
from app.services.audit_service import log_action
from app.utils.timeutils import now_utc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '-'}|{body.email.lower()}"
    if ratelimit.is_locked(key):
        raise HTTPException(429, "Too many failed attempts. Try again later.")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        ratelimit.register_failure(key)
        log_action(db, None, "login_failed", "user", None, {"email": body.email.lower()}, request)
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    ratelimit.reset(key)
    user.last_login_at = now_utc()
    log_action(db, user, "login", "user", user.id, None, request)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    body: ChangePassword, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    log_action(db, user, "password_changed", "user", user.id, None, request)
    db.commit()
    return {"detail": "Password updated"}
