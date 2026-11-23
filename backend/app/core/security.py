import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
import numpy as np
from cryptography.fernet import Fernet

from app.core.config import settings


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------- camera API keys ----------
def generate_camera_key() -> str:
    return secrets.token_urlsafe(32)


def hash_camera_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_camera_key(key: str, key_hash: str) -> bool:
    return hmac.compare_digest(hash_camera_key(key), key_hash)


# ---------- biometric encryption ----------
@lru_cache
def _fernet() -> Fernet:
    if not settings.BIOMETRIC_ENCRYPTION_KEY:
        raise RuntimeError("BIOMETRIC_ENCRYPTION_KEY is not configured")
    return Fernet(settings.BIOMETRIC_ENCRYPTION_KEY.encode())


def encrypt_embedding(vec) -> bytes:
    arr = np.asarray(vec, dtype=np.float32)
    return _fernet().encrypt(arr.tobytes())


def decrypt_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(_fernet().decrypt(blob), dtype=np.float32)
