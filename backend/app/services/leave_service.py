from datetime import date, timedelta

from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Attendance, LeaveRequest
from app.models.enums import AttendanceSource, AttendanceStatus, LeaveStatus
from app.services.schedule_service import sessions_for
from app.utils.timeutils import local_date, now_utc


def approved_leave_exists(db: Session, employee_id: int, d: date) -> bool:
    return (
        db.scalar(
            select(LeaveRequest.id)
            .where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveStatus.approved,
                LeaveRequest.start_date <= d,
                LeaveRequest.end_date >= d,
            )
            .limit(1)
        )
        is not None
    )


def has_overlapping_leave(db: Session, employee_id: int, start: date, end: date, exclude_id: int | None = None) -> bool:
    stmt = select(LeaveRequest.id).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.pending, LeaveStatus.approved]),
        and_(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start),
    )
    if exclude_id:
        stmt = stmt.where(LeaveRequest.id != exclude_id)
    return db.scalar(stmt.limit(1)) is not None


def ensure_on_leave_rows(db: Session, employee_id: int, d: date) -> int:
    """Create On Leave attendance rows for every session the employee should work on `d`."""
    created = 0
    for schedule, session in sessions_for(db, employee_id, d):
        exists = db.scalar(
            select(Attendance.id).where(
                Attendance.employee_id == employee_id, Attendance.session_id == session.id, Attendance.work_date == d
            )
        )
        if exists:
            continue
        try:
            with db.begin_nested():
                db.add(
                    Attendance(
                        employee_id=employee_id,
                        schedule_id=schedule.id,
                        session_id=session.id,
                        work_date=d,
                        status=AttendanceStatus.on_leave,
                        source=AttendanceSource.auto,
                        remarks="Approved leave",
                    )
                )
                db.flush()
            created += 1
        except IntegrityError:
            pass
    return created


def materialize_leave(db: Session, leave: LeaveRequest) -> None:
    """On approval: mark On Leave for dates up to today. Future dates are handled by the finalizer."""
    today = local_date(now_utc())
    d = leave.start_date
    while d <= min(leave.end_date, today):
        ensure_on_leave_rows(db, leave.employee_id, d)
        d += timedelta(days=1)


def revoke_leave_rows(db: Session, leave: LeaveRequest) -> None:
    db.execute(
        delete(Attendance).where(
            Attendance.employee_id == leave.employee_id,
            Attendance.work_date >= leave.start_date,
            Attendance.work_date <= leave.end_date,
            Attendance.status == AttendanceStatus.on_leave,
            Attendance.source == AttendanceSource.auto,
        )
    )
