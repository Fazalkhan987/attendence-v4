from datetime import date, time

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Date, ForeignKey, Integer, String, Table, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

schedule_cameras = Table(
    "schedule_cameras",
    Base.metadata,
    Column("schedule_id", ForeignKey("schedules.id", ondelete="CASCADE"), primary_key=True),
    Column("camera_id", ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
)


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    working_days: Mapped[list] = mapped_column(JSON, nullable=False)  # 0=Mon ... 6=Sun
    grace_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    checkin_open_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # before start
    checkout_open_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)  # before end
    checkout_close_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)  # after end
    absent_verification_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # after end
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department = relationship("Department")
    sessions = relationship(
        "ScheduleSession",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleSession.start_time",
    )
    cameras = relationship("Camera", secondary=schedule_cameras)
    assignments = relationship("ScheduleAssignment", back_populates="schedule", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("grace_minutes >= 0", name="ck_schedule_grace_nonneg"),
        UniqueConstraint("department_id", "name", name="uq_schedule_dept_name"),
    )


class ScheduleSession(Base):
    """One working session (e.g. Morning 09:00-12:00). A schedule has one or more."""

    __tablename__ = "schedule_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    schedule = relationship("Schedule", back_populates="sessions")

    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_session_times"),)


class ScheduleAssignment(Base, TimestampMixin):
    __tablename__ = "schedule_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)

    schedule = relationship("Schedule", back_populates="assignments")
    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("schedule_id", "employee_id", "effective_from", name="uq_assignment"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_assignment_range"),
    )
