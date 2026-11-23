from datetime import date, time

from pydantic import BaseModel, Field, field_validator, model_validator


class SessionIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=80)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check(self):
        if self.end_time <= self.start_time:
            raise ValueError("Session end time must be after start time")
        return self


class SessionOut(BaseModel):
    id: int
    name: str
    start_time: time
    end_time: time


class ScheduleBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    department_id: int
    working_days: list[int] = Field(min_length=1)
    grace_minutes: int = Field(default=15, ge=0, le=240)
    checkin_open_minutes: int = Field(default=30, ge=0, le=360)
    checkout_open_minutes: int = Field(default=15, ge=0, le=240)
    checkout_close_minutes: int = Field(default=120, ge=0, le=720)
    absent_verification_minutes: int = Field(default=30, ge=0, le=720)
    camera_ids: list[int] = []
    sessions: list[SessionIn] = Field(min_length=1)
    is_active: bool = True

    @field_validator("working_days")
    @classmethod
    def _days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("working_days must be integers 0 (Mon) to 6 (Sun)")
        return sorted(set(v))

    @model_validator(mode="after")
    def _no_overlap(self):
        ordered = sorted(self.sessions, key=lambda s: s.start_time)
        for a, b in zip(ordered, ordered[1:]):
            if b.start_time < a.end_time:
                raise ValueError(f"Sessions '{a.name}' and '{b.name}' overlap")
        return self


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(ScheduleBase):
    pass


class ScheduleOut(BaseModel):
    id: int
    name: str
    department_id: int
    department_name: str
    working_days: list[int]
    grace_minutes: int
    checkin_open_minutes: int
    checkout_open_minutes: int
    checkout_close_minutes: int
    absent_verification_minutes: int
    camera_ids: list[int]
    camera_codes: list[str]
    sessions: list[SessionOut]
    is_active: bool
    assigned_count: int = 0


class AssignRequest(BaseModel):
    employee_ids: list[int] = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _range(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class AssignmentOut(BaseModel):
    id: int
    schedule_id: int
    employee_id: int
    employee_code: str
    employee_name: str
    effective_from: date
    effective_to: date | None


class AssignmentUpdate(BaseModel):
    effective_to: date | None = None
