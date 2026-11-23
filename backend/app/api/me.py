"""Personal (employee) endpoints. Every query is scoped to the authenticated employee."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.leave import leave_out, leave_query
from app.core.deps import require_employee
from app.database import get_db
from app.models import Attendance, Employee, LeaveRequest, LeaveType, Schedule, ScheduleAssignment, User
from app.models.enums import LeaveStatus
from app.schemas.attendance import AttendanceOut
from app.schemas.leave import LeaveCreate, LeaveOut, LeaveTypeOut
from app.schemas.organization import EmployeeOut
from app.schemas.schedule import ScheduleOut
from app.services import employee_service as es
from app.services.attendance_service import attendance_out
from app.services.audit_service import log_action
from app.services.leave_service import has_overlapping_leave
from app.services.report_service import attendance_query
from app.services.schedule_service import schedule_to_out
from app.utils.timeutils import local_date, now_utc
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/me", tags=["employee self-service"])


@router.get("/profile", response_model=EmployeeOut)
def my_profile(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    e = es.get_employee_or_404(db, user.employee_id)
    return es.employee_out(e, es.face_counts(db, [e.id]))


@router.get("/schedules", response_model=list[ScheduleOut])
def my_schedules(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    today = local_date(now_utc())
    stmt = (
        select(Schedule)
        .join(ScheduleAssignment, ScheduleAssignment.schedule_id == Schedule.id)
        .where(
            ScheduleAssignment.employee_id == user.employee_id,
            Schedule.is_active.is_(True),
            (ScheduleAssignment.effective_to.is_(None)) | (ScheduleAssignment.effective_to >= today),
        )
        .options(selectinload(Schedule.sessions), selectinload(Schedule.cameras), selectinload(Schedule.department))
    )
    return [schedule_to_out(s) for s in db.scalars(stmt).unique()]


@router.get("/attendance", response_model=list[AttendanceOut])
def my_attendance(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(300, le=1000),
    offset: int = 0,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    stmt = attendance_query(date_from, date_to, employee_id=user.employee_id).limit(limit).offset(offset)
    return [attendance_out(a) for a in db.scalars(stmt).unique()]


@router.get("/leave-types", response_model=list[LeaveTypeOut])
def leave_types(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    return db.scalars(select(LeaveType).where(LeaveType.is_active.is_(True)).order_by(LeaveType.name)).all()


@router.get("/leave", response_model=list[LeaveOut])
def my_leave(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    rows = db.scalars(leave_query().where(LeaveRequest.employee_id == user.employee_id).order_by(LeaveRequest.created_at.desc())).unique()
    return [leave_out(l) for l in rows]


@router.post("/leave", response_model=LeaveOut, status_code=201)
def submit_leave(body: LeaveCreate, request: Request, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    lt = db.get(LeaveType, body.leave_type_id)
    if not lt or not lt.is_active:
        raise HTTPException(400, "Invalid leave type")
    if body.start_date < local_date(now_utc()):
        raise HTTPException(400, "Leave cannot start in the past. Ask an administrator to correct past attendance.")
    # lock the employee row so two simultaneous submissions cannot overlap
    db.scalar(select(Employee.id).where(Employee.id == user.employee_id).with_for_update())
    if has_overlapping_leave(db, user.employee_id, body.start_date, body.end_date):
        raise HTTPException(409, "You already have a pending or approved leave request covering one of these days")
    l = LeaveRequest(employee_id=user.employee_id, leave_type_id=lt.id, start_date=body.start_date, end_date=body.end_date, reason=body.reason)
    db.add(l)
    db.flush()
    log_action(db, user, "leave_submitted", "leave_request", l.id, {"start": str(l.start_date), "end": str(l.end_date)}, request)
    db.commit()
    return leave_out(db.scalar(leave_query().where(LeaveRequest.id == l.id)))


@router.delete("/leave/{leave_id}")
def cancel_my_leave(leave_id: int, request: Request, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    l = db.get(LeaveRequest, leave_id)
    if not l or l.employee_id != user.employee_id:
        raise HTTPException(404, "Leave request not found")
    if l.status != LeaveStatus.pending:
        raise HTTPException(409, "Only pending requests can be cancelled")
    l.status = LeaveStatus.cancelled
    log_action(db, user, "leave_cancelled", "leave_request", l.id, None, request)
    db.commit()
    return {"detail": "Leave request cancelled"}
