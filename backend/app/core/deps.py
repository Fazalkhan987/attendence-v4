from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, verify_camera_key
from app.database import get_db
from app.models import Camera, User
from app.models.enums import Role

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def require_employee(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.employee or user.employee_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Employee account required")
    return user


def get_camera(
    x_camera_code: str = Header(..., alias="X-Camera-Code"),
    x_camera_key: str = Header(..., alias="X-Camera-Key"),
    db: Session = Depends(get_db),
) -> Camera:
    camera = db.scalar(select(Camera).where(Camera.camera_code == x_camera_code))
    if camera is None or not verify_camera_key(x_camera_key, camera.api_key_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid camera credentials")
    if not camera.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Camera is disabled")
    return camera
