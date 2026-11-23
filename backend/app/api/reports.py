from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Attendance, Camera, Employee, LeaveRequest, RecognitionEvent, User
from app.models.enums import AttendanceStatus, EmploymentStatus, EventOutcome, LeaveStatus
from app.schemas.attendance import EmployeeSummary
from app.services.report_service import attendance_query, summarize, to_csv
from app.utils.timeutils import local_date, now_utc

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    today = local_date(now_utc())
    by_status = dict(
        db.execute(select(Attendance.status, func.count(Attendance.id)).where(Attendance.work_date == today).group_by(Attendance.status)).all()
    )
    start_week = today - timedelta(days=6)
    trend_rows = db.execute(
        select(Attendance.work_date, Attendance.status, func.count(Attendance.id))
        .where(Attendance.work_date >= start_week, Attendance.work_date <= today)
        .group_by(Attendance.work_date, Attendance.status)
    ).all()
    trend: dict[str, dict] = {}
    for d, st, c in trend_rows:
        trend.setdefault(d.isoformat(), {})[st.value] = c
    return {
        "date": today.isoformat(),
        "active_employees": db.scalar(select(func.count(Employee.id)).where(Employee.employment_status == EmploymentStatus.active)) or 0,
        "enrolled_employees": db.scalar(select(func.count(func.distinct(Employee.id))).where(Employee.embeddings.any())) or 0,
        "today": {s.value: by_status.get(s, 0) for s in AttendanceStatus},
        "pending_leave": db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == LeaveStatus.pending)) or 0,
        "active_cameras": db.scalar(select(func.count(Camera.id)).where(Camera.is_active.is_(True))) or 0,
        "events_today": db.scalar(select(func.count(RecognitionEvent.id)).where(RecognitionEvent.event_timestamp >= now_utc() - timedelta(hours=24))) or 0,
        "accepted_events_today": db.scalar(
            select(func.count(RecognitionEvent.id)).where(
                RecognitionEvent.event_timestamp >= now_utc() - timedelta(hours=24), RecognitionEvent.outcome == EventOutcome.accepted
            )
        ) or 0,
        "week_trend": trend,
    }


@router.get("/attendance-summary", response_model=list[EmployeeSummary])
def attendance_summary(
    date_from: date,
    date_to: date,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = list(db.scalars(attendance_query(date_from, date_to, employee_id, department_id)).unique())
    return summarize(rows)


@router.get("/attendance.csv")
def attendance_csv(
    date_from: date,
    date_to: date,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = list(db.scalars(attendance_query(date_from, date_to, employee_id, department_id)).unique())
    return Response(
        to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="attendance_{date_from}_{date_to}.csv"'},
    )
