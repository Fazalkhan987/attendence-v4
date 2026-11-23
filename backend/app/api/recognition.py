from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_camera, require_admin
from app.database import get_db
from app.models import Camera, RecognitionEvent, User
from app.models.enums import EventOutcome
from app.schemas.recognition import RecognitionEventIn, RecognitionEventOut, RecognitionResult
from app.services.attendance_service import process_recognition_event
from app.services.audit_service import log_action
from app.services.face_service import build_gallery

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.post("/events", response_model=RecognitionResult)
def receive_event(body: RecognitionEventIn, camera: Camera = Depends(get_camera), db: Session = Depends(get_db)):
    """Called by the face engine (camera credentials in X-Camera-Code / X-Camera-Key headers)."""
    if body.camera_id != camera.camera_code:
        raise HTTPException(403, "camera_id does not match the authenticated camera")
    ev, replayed = process_recognition_event(db, camera, body)
    return RecognitionResult(
        event_id=ev.event_id,
        outcome=EventOutcome.duplicate if replayed else ev.outcome,
        action=None if replayed else ev.action,
        reason="replayed_event" if replayed else ev.reason,
        attendance_id=ev.attendance_id,
    )


@router.get("/gallery")
def gallery(
    request: Request,
    since_version: str | None = None,
    camera: Camera = Depends(get_camera),
    db: Session = Depends(get_db),
):
    """Embeddings for the face engine to match against (camera-authenticated; never exposed to the browser)."""
    g = build_gallery(db, since_version)
    if not g["unchanged"]:
        log_action(db, None, "gallery_fetched", "camera", camera.id, {"camera_code": camera.camera_code, "employees": len(g["employees"])}, request)
        db.commit()
    return g


@router.get("/events", response_model=list[RecognitionEventOut])
def list_events(
    outcome: EventOutcome | None = None,
    employee_code: str | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(RecognitionEvent).options(selectinload(RecognitionEvent.employee))
    if outcome:
        stmt = stmt.where(RecognitionEvent.outcome == outcome)
    if employee_code:
        stmt = stmt.where(RecognitionEvent.employee_code == employee_code)
    rows = db.scalars(stmt.order_by(RecognitionEvent.event_timestamp.desc()).limit(limit).offset(offset)).all()
    return [
        {
            "id": e.id, "event_id": e.event_id, "employee_code": e.employee_code,
            "employee_name": e.employee.full_name if e.employee else None, "camera_code": e.camera_code,
            "confidence": e.confidence, "event_timestamp": e.event_timestamp, "received_at": e.received_at,
            "outcome": e.outcome, "action": e.action, "reason": e.reason, "attendance_id": e.attendance_id,
        }
        for e in rows
    ]
