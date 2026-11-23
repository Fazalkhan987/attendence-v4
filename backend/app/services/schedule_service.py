from datetime import date

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Employee, Schedule, ScheduleAssignment, ScheduleSession


def sessions_for(db: Session, employee_id: int, d: date) -> list[tuple[Schedule, ScheduleSession]]:
    """All (schedule, session) pairs the employee is expected to work on date `d`."""
    stmt = (
        select(Schedule, ScheduleSession)
        .join(ScheduleSession, ScheduleSession.schedule_id == Schedule.id)
        .join(ScheduleAssignment, ScheduleAssignment.schedule_id == Schedule.id)
        .where(
            ScheduleAssignment.employee_id == employee_id,
            Schedule.is_active.is_(True),
            ScheduleAssignment.effective_from <= d,
            or_(ScheduleAssignment.effective_to.is_(None), ScheduleAssignment.effective_to >= d),
        )
        .order_by(ScheduleSession.start_time)
    )
    pairs = [(s, ss) for s, ss in db.execute(stmt).all() if d.weekday() in (s.working_days or [])]
    # de-duplicate (same schedule assigned twice with different effective ranges)
    seen, out = set(), []
    for s, ss in pairs:
        if ss.id not in seen:
            seen.add(ss.id)
            out.append((s, ss))
    return out


def schedule_to_out(s: Schedule, assigned_count: int = 0) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "department_id": s.department_id,
        "department_name": s.department.name if s.department else "",
        "working_days": s.working_days,
        "grace_minutes": s.grace_minutes,
        "checkin_open_minutes": s.checkin_open_minutes,
        "checkout_open_minutes": s.checkout_open_minutes,
        "checkout_close_minutes": s.checkout_close_minutes,
        "absent_verification_minutes": s.absent_verification_minutes,
        "camera_ids": [c.id for c in s.cameras],
        "camera_codes": [c.camera_code for c in s.cameras],
        "sessions": [{"id": x.id, "name": x.name, "start_time": x.start_time, "end_time": x.end_time} for x in s.sessions],
        "is_active": s.is_active,
        "assigned_count": assigned_count,
    }


def load_schedule(db: Session, schedule_id: int) -> Schedule:
    s = db.scalar(
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(selectinload(Schedule.sessions), selectinload(Schedule.cameras), selectinload(Schedule.department))
    )
    if not s:
        raise HTTPException(404, "Schedule not found")
    return s


def check_assignment_conflict(db: Session, schedule: Schedule, employee: Employee, start: date, end: date | None) -> None:
    """An employee cannot have overlapping sessions from two schedules on the same weekday/date range."""
    if employee.department_id != schedule.department_id:
        raise HTTPException(400, f"{employee.employee_code} belongs to a different department than this schedule")
    stmt = (
        select(Schedule, ScheduleAssignment)
        .join(ScheduleAssignment, ScheduleAssignment.schedule_id == Schedule.id)
        .where(
            ScheduleAssignment.employee_id == employee.id,
            Schedule.is_active.is_(True),
            Schedule.id != schedule.id,
        )
        .options(selectinload(Schedule.sessions))
    )
    for other, asg in db.execute(stmt).all():
        range_overlap = (asg.effective_to is None or asg.effective_to >= start) and (end is None or end >= asg.effective_from)
        if not range_overlap:
            continue
        if not set(other.working_days) & set(schedule.working_days):
            continue
        for a in schedule.sessions:
            for b in other.sessions:
                if a.start_time < b.end_time and b.start_time < a.end_time:
                    raise HTTPException(
                        409,
                        f"{employee.employee_code} already has overlapping hours in schedule '{other.name}'",
                    )
