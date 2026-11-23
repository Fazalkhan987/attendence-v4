from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime, enum_col
from app.models.enums import Role


class User(Base, TimestampMixin):
    """Authentication account. Kept separate from the employee (HR) record."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[Role] = mapped_column(enum_col(Role), nullable=False, default=Role.employee)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    employee = relationship("Employee", back_populates="user")
