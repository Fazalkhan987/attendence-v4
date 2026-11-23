from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.database import get_db
from app.models import AuditLog, User
from app.utils.timeutils import at_local

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditOut(BaseModel):
    id: int
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime


@router.get("", response_model=list[AuditOut])
def list_audit(
    action: str | None = None,
    entity_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(AuditLog).options(selectinload(AuditLog.user))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= at_local(date_from, time(0, 0)))
    if date_to:
        stmt = stmt.where(AuditLog.created_at < at_local(date_to, time(0, 0)) + timedelta(days=1))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return [
        {
            "id": r.id, "user_email": r.user.email if r.user else None, "action": r.action, "entity_type": r.entity_type,
            "entity_id": r.entity_id, "details": r.details, "ip_address": r.ip_address, "created_at": r.created_at,
        }
        for r in rows
    ]
