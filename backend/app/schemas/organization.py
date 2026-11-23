from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import EmploymentStatus


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    is_active: bool | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    employee_count: int = 0


class AccountIn(BaseModel):
    login_email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    is_active: bool = True


class AccountUpdate(BaseModel):
    login_email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    is_active: bool | None = None


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    department_id: int
    designation: str = Field(min_length=1, max_length=120)
    joining_date: date
    employment_status: EmploymentStatus = EmploymentStatus.active
    supervisor_id: int | None = None
    face_consent: bool = False
    account: AccountIn | None = None


class EmployeeUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    department_id: int | None = None
    designation: str | None = None
    joining_date: date | None = None
    employment_status: EmploymentStatus | None = None
    supervisor_id: int | None = None
    face_consent: bool | None = None


class EmployeeOut(BaseModel):
    id: int
    employee_code: str
    full_name: str
    email: str
    phone: str | None
    address: str | None
    has_photo: bool
    department_id: int
    department_name: str
    designation: str
    joining_date: date
    employment_status: EmploymentStatus
    supervisor_id: int | None
    supervisor_name: str | None
    face_consent: bool
    face_consent_at: datetime | None
    face_samples: int
    has_account: bool
    login_email: str | None
    account_active: bool | None


class EnrollRequest(BaseModel):
    images: list[str] = Field(min_length=1, description="base64 encoded JPEG/PNG frames (data-URL prefix allowed)")
    replace_existing: bool = True
    set_profile_photo: bool = True


class EnrollResult(BaseModel):
    accepted: int
    rejected: list[dict]
    total_samples: int
