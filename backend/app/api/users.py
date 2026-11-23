from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models import User
from app.models.enums import Role
from app.schemas.auth import AdminCreate, UserOut, UserUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/admins", response_model=list[UserOut])
def list_admins(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).where(User.role == Role.admin).order_by(User.id)).all()


@router.post("/admins", response_model=UserOut, status_code=201)
def create_admin(body: AdminCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password), role=Role.admin)
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A user with this email already exists")
    log_action(db, admin, "admin_created", "user", u.id, {"email": u.email}, request)
    db.commit()
    return u


@router.patch("/admins/{user_id}", response_model=UserOut)
def update_admin(
    user_id: int, body: UserUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    u = db.get(User, user_id)
    if not u or u.role != Role.admin:
        raise HTTPException(404, "Administrator not found")
    if body.is_active is False and u.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.full_name:
        u.full_name = body.full_name
    if body.new_password:
        u.password_hash = hash_password(body.new_password)
    log_action(db, admin, "admin_updated", "user", u.id, {"fields": list(body.model_dump(exclude_none=True).keys())}, request)
    db.commit()
    return u
