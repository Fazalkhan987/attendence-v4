import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Attendance, Employee
from app.models.enums import AttendanceStatus
from app.services.attendance_service import format_local


def attendance_query(
    date_from: date | None = None,
    date_to: date | None = None,
    employee_id: int | None = None,
    department_id: int | None = None,
    status: AttendanceStatus | None = None,
):
    stmt = select(Attendance).options(
        joinedload(Attendance.employee).joinedload(Employee.department),
        joinedload(Attendance.schedule),
        joinedload(Attendance.session),
    )
    if date_from:
        stmt = stmt.where(Attendance.work_date >= date_from)
    if date_to:
        stmt = stmt.where(Attendance.work_date <= date_to)
    if employee_id:
        stmt = stmt.where(Attendance.employee_id == employee_id)
    if department_id:
        stmt = stmt.join(Employee, Employee.id == Attendance.employee_id).where(Employee.department_id == department_id)
    if status:
        stmt = stmt.where(Attendance.status == status)
    return stmt.order_by(Attendance.work_date.desc(), Attendance.employee_id, Attendance.session_id)


def summarize(rows: list[Attendance]) -> list[dict]:
    out: dict[int, dict] = {}
    for a in rows:
        s = out.setdefault(
            a.employee_id,
            {
                "employee_id": a.employee_id,
                "employee_code": a.employee.employee_code,
                "employee_name": a.employee.full_name,
                "department_name": a.employee.department.name if a.employee.department else "",
                "present": 0, "late": 0, "absent": 0, "on_leave": 0, "half_day": 0,
                "incomplete": 0, "excused": 0, "total_sessions": 0, "worked_minutes": 0,
            },
        )
        s[a.status.value] += 1
        s["total_sessions"] += 1
        s["worked_minutes"] += a.working_minutes or 0
    result = []
    for s in out.values():
        attended = s["present"] + s["late"] + s["half_day"] + s["excused"]
        counted = s["total_sessions"] - s["on_leave"]
        s["worked_hours"] = round(s.pop("worked_minutes") / 60, 2)
        s["attendance_rate"] = round(100 * attended / counted, 1) if counted else 0.0
        result.append(s)
    return sorted(result, key=lambda x: x["employee_code"])


def to_csv(rows: list[Attendance]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Employee ID", "Name", "Department", "Schedule", "Session", "Check-in", "Check-out",
                "Status", "Late (min)", "Worked (min)", "Early departure", "Source", "Remarks"])
    for a in rows:
        w.writerow([
            a.work_date.isoformat(), a.employee.employee_code, a.employee.full_name,
            a.employee.department.name if a.employee.department else "", a.schedule.name, a.session.name,
            format_local(a.check_in_time), format_local(a.check_out_time), a.status.value, a.late_minutes,
            a.working_minutes if a.working_minutes is not None else "", "yes" if a.early_departure else "",
            a.source.value, a.remarks or "",
        ])
    return buf.getvalue()
