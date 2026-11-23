from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LeaveStatus


class LeaveTypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    is_active: bool = True


class LeaveTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_active: bool


class LeaveCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected", "cancelled"]
    note: str | None = Field(default=None, max_length=500)


class LeaveOut(BaseModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department_name: str
    leave_type_id: int
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: str | None
    status: LeaveStatus
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
