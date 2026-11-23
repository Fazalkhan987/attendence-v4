from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.database import get_db
from app.models import Attendance, AttendanceCorrection, Employee, ScheduleSession, User
from app.models.enums import AttendanceSource, AttendanceStatus
from app.schemas.attendance import AttendanceOut, AttendanceUpdate, CorrectionOut, ManualAttendanceCreate
from app.services.attendance_service import (
    apply_correction,
    attendance_out,
    employee_sessions_pair,
    recompute_duration,
    snapshot,
)
from app.services.audit_service import log_action
from app.services.report_service import attendance_query
from app.utils.timeutils import ensure_utc

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _load(db: Session, attendance_id: int) -> Attendance:
    a = db.scalar(attendance_query().where(Attendance.id == attendance_id))
    if not a:
        raise HTTPException(404, "Attendance record not found")
    return a


@router.get("", response_model=list[AttendanceOut])
def list_attendance(
    date_from: date | None = None,
    date_to: date | None = None,
    employee_id: int | None = None,
    department_id: int | None = None,
    status: AttendanceStatus | None = None,
    limit: int = Query(300, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = attendance_query(date_from, date_to, employee_id, department_id, status).limit(limit).offset(offset)
    return [attendance_out(a) for a in db.scalars(stmt).unique()]


@router.post("/manual", response_model=AttendanceOut, status_code=201)
def create_manual(body: ManualAttendanceCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    emp = db.get(Employee, body.employee_id)
    sess = db.get(ScheduleSession, body.session_id)
    if not emp or not sess:
        raise HTTPException(404, "Employee or session not found")
    sched = employee_sessions_pair(db, emp.id, sess.id)
    if not sched:
        raise HTTPException(400, "Employee is not assigned to the schedule of this session")
    if body.status in (AttendanceStatus.present, AttendanceStatus.late, AttendanceStatus.half_day) and not body.check_in_time:
        raise HTTPException(400, "check_in_time is required for this status")
    a = Attendance(
        employee_id=emp.id, schedule_id=sched.id, session_id=sess.id, work_date=body.work_date, status=body.status,
        check_in_time=ensure_utc(body.check_in_time) if body.check_in_time else None,
        check_out_time=ensure_utc(body.check_out_time) if body.check_out_time else None,
        source=AttendanceSource.manual, remarks=body.remarks,
    )
    recompute_duration(a)
    try:
        with db.begin_nested():
            db.add(a)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "Attendance already exists for this employee, session and date. Edit it instead.")
    db.add(AttendanceCorrection(attendance_id=a.id, employee_id=emp.id, old_values=None, new_values=snapshot(a), reason=body.reason, corrected_by=admin.id))
    log_action(db, admin, "attendance_created_manually", "attendance", a.id, {"employee_id": emp.id, "date": str(body.work_date)}, request)
    db.commit()
    return attendance_out(_load(db, a.id))


@router.patch("/{attendance_id}", response_model=AttendanceOut)
def correct_attendance(
    attendance_id: int, body: AttendanceUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    a = _load(db, attendance_id)
    changes = body.model_dump(exclude={"reason"}, exclude_unset=True)
    if not changes:
        raise HTTPException(400, "No changes supplied")
    try:
        corr = apply_correction(db, admin, a, changes, body.reason)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    log_action(db, admin, "attendance_corrected", "attendance", a.id, {"reason": body.reason}, request)
    db.commit()
    return attendance_out(_load(db, a.id))


@router.get("/{attendance_id}/corrections", response_model=list[CorrectionOut])
def list_corrections(attendance_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.scalars(
        select(AttendanceCorrection)
        .where(AttendanceCorrection.attendance_id == attendance_id)
        .options(selectinload(AttendanceCorrection.editor))
        .order_by(AttendanceCorrection.id.desc())
    ).all()
    return [
        {
            "id": c.id, "attendance_id": c.attendance_id, "employee_id": c.employee_id, "old_values": c.old_values,
            "new_values": c.new_values, "reason": c.reason, "corrected_by": c.corrected_by,
            "corrected_by_name": (c.editor.full_name or c.editor.email) if c.editor else None, "created_at": c.created_at,
        }
        for c in rows
    ]
