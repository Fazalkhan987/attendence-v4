from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.security import generate_camera_key, hash_camera_key
from app.database import get_db
from app.models import Camera, Department, User
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate, CameraWithKey
from app.services.audit_service import log_action

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _with_key(c: Camera, key: str) -> dict:
    return {**CameraOut.model_validate(c).model_dump(), "api_key": key}


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(Camera).order_by(Camera.camera_code)).all()


@router.post("", response_model=CameraWithKey, status_code=201)
def create_camera(body: CameraCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.department_id and not db.get(Department, body.department_id):
        raise HTTPException(400, "Department does not exist")
    key = generate_camera_key()
    cam = Camera(**body.model_dump(), api_key_hash=hash_camera_key(key))
    db.add(cam)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Camera code already exists")
    log_action(db, admin, "camera_created", "camera", cam.id, {"camera_code": cam.camera_code}, request)
    db.commit()
    return _with_key(cam, key)


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, body: CameraUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("department_id") and not db.get(Department, changes["department_id"]):
        raise HTTPException(400, "Department does not exist")
    for k, v in changes.items():
        setattr(cam, k, v)
    log_action(db, admin, "camera_updated", "camera", cam.id, {"fields": list(changes.keys())}, request)
    db.commit()
    return cam


@router.post("/{camera_id}/rotate-key", response_model=CameraWithKey)
def rotate_key(camera_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    key = generate_camera_key()
    cam.api_key_hash = hash_camera_key(key)
    log_action(db, admin, "camera_key_rotated", "camera", cam.id, None, request)
    db.commit()
    return _with_key(cam, key)


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    log_action(db, admin, "camera_deleted", "camera", cam.id, {"camera_code": cam.camera_code}, request)
    db.delete(cam)
    db.commit()
    return {"detail": "Camera deleted"}
