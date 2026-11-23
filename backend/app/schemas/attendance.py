from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AttendanceSource, AttendanceStatus


class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department_name: str
    schedule_name: str
    session_id: int
    session_name: str
    session_start: time
    session_end: time
    work_date: date
    check_in_time: datetime | None
    check_out_time: datetime | None
    status: AttendanceStatus
    late_minutes: int
    working_minutes: int | None
    early_departure: bool
    source: AttendanceSource
    remarks: str | None


class AttendanceUpdate(BaseModel):
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    clear_check_out: bool = False
    status: AttendanceStatus | None = None
    remarks: str | None = None
    reason: str = Field(min_length=3, description="Why this change is made (audited)")


class ManualAttendanceCreate(BaseModel):
    employee_id: int
    session_id: int
    work_date: date
    status: AttendanceStatus
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    remarks: str | None = None
    reason: str = Field(min_length=3)

    @model_validator(mode="after")
    def _times(self):
        if self.check_in_time and self.check_out_time and self.check_out_time < self.check_in_time:
            raise ValueError("check_out_time cannot be before check_in_time")
        return self


class CorrectionOut(BaseModel):
    id: int
    attendance_id: int
    employee_id: int
    old_values: dict | None
    new_values: dict
    reason: str
    corrected_by: int | None
    corrected_by_name: str | None
    created_at: datetime


class EmployeeSummary(BaseModel):
    employee_id: int
    employee_code: str
    employee_name: str
    department_name: str
    present: int = 0
    late: int = 0
    absent: int = 0
    on_leave: int = 0
    half_day: int = 0
    incomplete: int = 0
    excused: int = 0
    total_sessions: int = 0
    worked_hours: float = 0.0
    attendance_rate: float = 0.0
