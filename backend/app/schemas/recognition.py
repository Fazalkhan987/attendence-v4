from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EventOutcome


class RecognitionEventIn(BaseModel):
    """Only what the face engine knows. Names, departments, schedules and statuses stay in the backend."""

    employee_id: str = Field(min_length=1, max_length=50, description="Employee code, e.g. EMP-001")
    camera_id: str = Field(min_length=1, max_length=50, description="Camera code, e.g. CAM-01")
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    event_id: str | None = Field(default=None, max_length=64, description="Unique id (UUID) used for replay protection")


class RecognitionResult(BaseModel):
    event_id: str
    outcome: EventOutcome
    action: str | None = None
    reason: str | None = None
    attendance_id: int | None = None


class RecognitionEventOut(BaseModel):
    id: int
    event_id: str
    employee_code: str
    employee_name: str | None
    camera_code: str
    confidence: float
    event_timestamp: datetime
    received_at: datetime
    outcome: EventOutcome
    action: str | None
    reason: str | None
    attendance_id: int | None
