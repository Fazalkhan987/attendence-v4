from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Employee, LeaveRequest, LeaveType, User
from app.models.enums import LeaveStatus, Role
from app.schemas.leave import LeaveDecision, LeaveOut, LeaveTypeIn, LeaveTypeOut
from app.services.audit_service import log_action
from app.services.leave_service import materialize_leave, revoke_leave_rows
from app.utils.timeutils import now_utc

router = APIRouter(prefix="/leave", tags=["leave"])


def leave_query():
    return select(LeaveRequest).options(
        joinedload(LeaveRequest.employee).joinedload(Employee.department),
        joinedload(LeaveRequest.leave_type),
        joinedload(LeaveRequest.reviewer),
    )


def leave_out(l: LeaveRequest) -> dict:
    return {
        "id": l.id,
        "employee_id": l.employee_id,
        "employee_code": l.employee.employee_code,
        "employee_name": l.employee.full_name,
        "department_name": l.employee.department.name if l.employee.department else "",
        "leave_type_id": l.leave_type_id,
        "leave_type": l.leave_type.name,
        "start_date": l.start_date,
        "end_date": l.end_date,
        "days": (l.end_date - l.start_date).days + 1,
        "reason": l.reason,
        "status": l.status,
        "reviewed_by_name": (l.reviewer.full_name or l.reviewer.email) if l.reviewer else None,
        "reviewed_at": l.reviewed_at,
        "review_note": l.review_note,
        "created_at": l.created_at,
    }


# ---------- leave types ----------
@router.get("/types", response_model=list[LeaveTypeOut])
def list_types(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(LeaveType).order_by(LeaveType.name)
    if not include_inactive or user.role != Role.admin:
        stmt = stmt.where(LeaveType.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post("/types", response_model=LeaveTypeOut, status_code=201)
def create_type(body: LeaveTypeIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    t = LeaveType(name=body.name.strip(), is_active=body.is_active)
    db.add(t)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Leave type already exists")
    log_action(db, admin, "leave_type_created", "leave_type", t.id, {"name": t.name}, request)
    db.commit()
    return t


@router.put("/types/{type_id}", response_model=LeaveTypeOut)
def update_type(type_id: int, body: LeaveTypeIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    t = db.get(LeaveType, type_id)
    if not t:
        raise HTTPException(404, "Leave type not found")
    t.name, t.is_active = body.name.strip(), body.is_active
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Leave type already exists")
    log_action(db, admin, "leave_type_updated", "leave_type", t.id, {"name": t.name}, request)
    db.commit()
    return t


# ---------- admin management of requests ----------
@router.get("", response_model=list[LeaveOut])
def list_leave(
    status: LeaveStatus | None = None,
    employee_id: int | None = None,
    department_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(300, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = leave_query()
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if department_id:
        stmt = stmt.join(Employee, Employee.id == LeaveRequest.employee_id).where(Employee.department_id == department_id)
    if date_from:
        stmt = stmt.where(LeaveRequest.end_date >= date_from)
    if date_to:
        stmt = stmt.where(LeaveRequest.start_date <= date_to)
    rows = db.scalars(stmt.order_by(LeaveRequest.created_at.desc()).limit(limit)).unique()
    return [leave_out(l) for l in rows]


@router.post("/{leave_id}/decision", response_model=LeaveOut)
def decide(leave_id: int, body: LeaveDecision, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    l = db.scalar(leave_query().where(LeaveRequest.id == leave_id))
    if not l:
        raise HTTPException(404, "Leave request not found")
    if body.decision == "cancelled":
        if l.status not in (LeaveStatus.pending, LeaveStatus.approved):
            raise HTTPException(409, "Only pending or approved leave can be cancelled")
        was_approved = l.status == LeaveStatus.approved
        l.status = LeaveStatus.cancelled
        if was_approved:
            revoke_leave_rows(db, l)
    else:
        if l.status != LeaveStatus.pending:
            raise HTTPException(409, f"Request is already {l.status.value}")
        l.status = LeaveStatus.approved if body.decision == "approved" else LeaveStatus.rejected
    l.reviewed_by = admin.id
    l.reviewed_at = now_utc()
    l.review_note = body.note
    db.flush()
    if l.status == LeaveStatus.approved:
        materialize_leave(db, l)
    log_action(db, admin, f"leave_{l.status.value}", "leave_request", l.id, {"employee_id": l.employee_id}, request)
    db.commit()
    return leave_out(db.scalar(leave_query().where(LeaveRequest.id == l.id)))
