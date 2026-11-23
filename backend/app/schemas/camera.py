from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CameraPurpose


class CameraCreate(BaseModel):
    camera_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=120)
    location: str | None = None
    department_id: int | None = None
    purpose: CameraPurpose = CameraPurpose.both
    source: str | None = None
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    department_id: int | None = None
    purpose: CameraPurpose | None = None
    source: str | None = None
    is_active: bool | None = None


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_code: str
    name: str
    location: str | None
    department_id: int | None
    purpose: CameraPurpose
    source: str | None
    is_active: bool
    last_seen_at: datetime | None


class CameraWithKey(CameraOut):
    api_key: str  # shown once
