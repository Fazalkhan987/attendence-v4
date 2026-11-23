import base64
import hashlib
import os
import uuid
from pathlib import Path

import httpx
import numpy as np
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_embedding, encrypt_embedding
from app.models import Employee, FaceEmbedding
from app.models.enums import EmploymentStatus


def _strip_data_url(b64: str) -> str:
    return b64.split(",", 1)[1] if b64.startswith("data:") and "," in b64 else b64


def request_embeddings(images_b64: list[str]) -> list[dict]:
    """Ask the face engine service to detect, quality-check and embed the images."""
    try:
        r = httpx.post(
            f"{settings.FACE_ENGINE_URL}/v1/embed",
            json={"images": images_b64},
            headers={"X-Service-Key": settings.FACE_ENGINE_SERVICE_KEY},
            timeout=120,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "Face engine service is not reachable. Start it with: python -m face_engine.service")
    if r.status_code != 200:
        raise HTTPException(502, f"Face engine error ({r.status_code})")
    return r.json()["results"]


def photo_dir() -> Path:
    p = Path(settings.UPLOAD_DIR) / "photos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def enroll_employee(db: Session, employee: Employee, images: list[str], replace: bool, set_photo: bool) -> dict:
    if not employee.face_consent:
        raise HTTPException(400, "Employee has not given biometric consent. Record consent before enrollment.")
    if employee.employment_status != EmploymentStatus.active:
        raise HTTPException(400, "Employee is not active")
    if len(images) > settings.MAX_ENROLL_IMAGES:
        raise HTTPException(400, f"At most {settings.MAX_ENROLL_IMAGES} images per enrollment")
    cleaned = [_strip_data_url(i) for i in images]
    raw_images = []
    for c in cleaned:
        try:
            raw = base64.b64decode(c, validate=False)
        except Exception:
            raise HTTPException(400, "Invalid base64 image")
        if len(raw) > settings.MAX_ENROLL_IMAGE_BYTES:
            raise HTTPException(413, "Image too large")
        raw_images.append(raw)

    results = request_embeddings(cleaned)
    ok = [(i, r) for i, r in enumerate(results) if r.get("ok")]
    rejected = [{"index": i, "reason": r.get("reason", "rejected")} for i, r in enumerate(results) if not r.get("ok")]
    if len(ok) < settings.MIN_ENROLL_SAMPLES:
        raise HTTPException(
            422,
            {"message": f"Need at least {settings.MIN_ENROLL_SAMPLES} good face samples, got {len(ok)}.", "rejected": rejected},
        )

    new = np.array([r["embedding"] for _, r in ok], dtype=np.float32)
    new /= np.linalg.norm(new, axis=1, keepdims=True) + 1e-9

    # Refuse if this face already belongs to another employee.
    others = db.execute(
        select(FaceEmbedding.embedding_encrypted, Employee.employee_code)
        .join(Employee, Employee.id == FaceEmbedding.employee_id)
        .where(FaceEmbedding.is_active.is_(True), FaceEmbedding.employee_id != employee.id)
    ).all()
    if others:
        mat = np.stack([decrypt_embedding(b) for b, _ in others])
        mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        sims = new @ mat.T
        if float(sims.max()) >= settings.DUPLICATE_FACE_THRESHOLD:
            _, col = np.unravel_index(int(sims.argmax()), sims.shape)
            raise HTTPException(409, f"This face is already enrolled for employee {others[int(col)][1]}")

    if replace:
        db.execute(delete(FaceEmbedding).where(FaceEmbedding.employee_id == employee.id))
    for (_, r), vec in zip(ok, new):
        db.add(
            FaceEmbedding(
                employee_id=employee.id,
                embedding_encrypted=encrypt_embedding(vec),
                quality_score=float(r.get("quality", 0.0)),
                model_name=r.get("model", "buffalo_l"),
            )
        )

    if set_photo:
        best_idx = max(ok, key=lambda t: t[1].get("quality", 0.0))[0]
        name = f"{employee.id}-{uuid.uuid4().hex[:10]}.jpg"
        (photo_dir() / name).write_bytes(raw_images[best_idx])
        if employee.photo_path:
            try:
                os.remove(photo_dir() / employee.photo_path)
            except OSError:
                pass
        employee.photo_path = name

    db.flush()
    total = db.scalar(select(func.count(FaceEmbedding.id)).where(FaceEmbedding.employee_id == employee.id)) or 0
    return {"accepted": len(ok), "rejected": rejected, "total_samples": total}


def build_gallery(db: Session, since_version: str | None = None) -> dict:
    """Embeddings for the recognition engine. Only active, consenting, active-status employees."""
    rows = db.execute(
        select(FaceEmbedding.id, FaceEmbedding.embedding_encrypted, Employee.employee_code)
        .join(Employee, Employee.id == FaceEmbedding.employee_id)
        .where(
            FaceEmbedding.is_active.is_(True),
            Employee.face_consent.is_(True),
            Employee.employment_status == EmploymentStatus.active,
        )
        .order_by(FaceEmbedding.id)
    ).all()
    version = hashlib.sha256(",".join(f"{r[0]}:{r[2]}" for r in rows).encode()).hexdigest()[:16]
    if since_version and since_version == version:
        return {"version": version, "unchanged": True, "employees": []}
    grouped: dict[str, list[list[float]]] = {}
    for _, blob, code in rows:
        vec = decrypt_embedding(blob)
        grouped.setdefault(code, []).append([round(float(x), 6) for x in vec])
    return {
        "version": version,
        "unchanged": False,
        "employees": [{"employee_id": c, "embeddings": e} for c, e in grouped.items()],
    }
