from datetime import date, datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime, enum_col, utcnow
from app.models.enums import AttendanceSource, AttendanceStatus


class Attendance(Base, TimestampMixin):
    """One row per employee per session per day."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("schedule_sessions.id", ondelete="RESTRICT"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    check_out_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[AttendanceStatus] = mapped_column(enum_col(AttendanceStatus), nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    working_minutes: Mapped[int | None] = mapped_column(Integer)
    early_departure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[AttendanceSource] = mapped_column(
        enum_col(AttendanceSource), default=AttendanceSource.auto, nullable=False
    )
    remarks: Mapped[str | None] = mapped_column(Text)

    employee = relationship("Employee")
    schedule = relationship("Schedule")
    session = relationship("ScheduleSession")
    corrections = relationship("AttendanceCorrection", back_populates="attendance", order_by="AttendanceCorrection.id")

    __table_args__ = (
        UniqueConstraint("employee_id", "session_id", "work_date", name="uq_attendance_emp_session_date"),
        CheckConstraint("check_out_time IS NULL OR check_in_time IS NULL OR check_out_time >= check_in_time", name="ck_attendance_times"),
        Index("ix_attendance_date", "work_date"),
        Index("ix_attendance_emp_date", "employee_id", "work_date"),
    )


class AttendanceCorrection(Base):
    """Immutable history of manual changes."""

    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    old_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    attendance = relationship("Attendance", back_populates="corrections")
    editor = relationship("User")
