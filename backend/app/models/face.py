from sqlalchemy import Boolean, Float, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FaceEmbedding(Base, TimestampMixin):
    """Encrypted ArcFace embedding. No face images are stored here."""

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    embedding_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    model_name: Mapped[str] = mapped_column(String(50), default="buffalo_l")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employee = relationship("Employee", back_populates="embeddings")
