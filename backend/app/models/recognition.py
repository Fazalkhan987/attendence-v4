from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime, enum_col, utcnow
from app.models.enums import EventOutcome


class RecognitionEvent(Base):
    """Raw (already confirmed) sighting sent by the face engine. Separate from attendance."""

    __tablename__ = "recognition_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # idempotency / replay key
    employee_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    camera_code: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    outcome: Mapped[EventOutcome] = mapped_column(enum_col(EventOutcome), default=EventOutcome.rejected, nullable=False)
    action: Mapped[str | None] = mapped_column(String(30))  # check_in / check_out / early_check_out
    reason: Mapped[str | None] = mapped_column(String(100))
    attendance_id: Mapped[int | None] = mapped_column(ForeignKey("attendance.id", ondelete="SET NULL"))

    employee = relationship("Employee")
    camera = relationship("Camera")

    __table_args__ = (
        Index("ix_events_emp_ts", "employee_id", "event_timestamp"),
        Index("ix_events_ts", "event_timestamp"),
    )
