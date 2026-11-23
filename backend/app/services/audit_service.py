from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_action(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Adds an audit row to the current transaction (caller commits). Never pass secrets/biometrics in details."""
    ip = request.client.host if request and request.client else None
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            ip_address=ip,
        )
    )
