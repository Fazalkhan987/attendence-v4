import enum


class Role(str, enum.Enum):
    admin = "admin"
    employee = "employee"


class EmploymentStatus(str, enum.Enum):
    active = "active"
    probation = "probation"
    suspended = "suspended"
    resigned = "resigned"
    terminated = "terminated"


class CameraPurpose(str, enum.Enum):
    entry = "entry"
    exit = "exit"
    both = "both"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    late = "late"
    absent = "absent"
    on_leave = "on_leave"
    half_day = "half_day"
    incomplete = "incomplete"
    excused = "excused"


class AttendanceSource(str, enum.Enum):
    auto = "auto"
    manual = "manual"


class EventOutcome(str, enum.Enum):
    accepted = "accepted"
    duplicate = "duplicate"
    ignored = "ignored"
    rejected = "rejected"


class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
