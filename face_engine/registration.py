"""Enrollment: turn captured frames into quality-checked face embeddings."""
import cv2
import numpy as np

from face_engine.config import Config
from face_engine.detection import FaceDetector, quality_issues


class EnrollmentProcessor:
    def __init__(self, detector: FaceDetector, cfg: Config):
        self.detector = detector
        self.cfg = cfg

    def process_image(self, data: bytes) -> dict:
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"ok": False, "reason": "unreadable_image"}
        faces = self.detector.detect(frame)
        if not faces:
            return {"ok": False, "reason": "no_face_detected"}
        if len(faces) > 1:
            return {"ok": False, "reason": "multiple_faces"}
        face = faces[0]
        problems, quality = quality_issues(
            face,
            frame,
            min_size=self.cfg.enroll_min_face_size,
            min_det=self.cfg.enroll_min_det_score,
            min_blur=self.cfg.enroll_min_blur,
            max_yaw=self.cfg.enroll_max_yaw,
            max_pitch=self.cfg.enroll_max_pitch,
        )
        if problems:
            return {"ok": False, "reason": problems[0]}
        return {
            "ok": True,
            "embedding": [float(x) for x in face.embedding],
            "quality": quality,
            "model": self.cfg.model_name,
        }

    def process(self, images: list[bytes]) -> list[dict]:
        results = [self.process_image(b) for b in images]
        # drop near-identical frames (same pose twice adds no information)
        kept: list[np.ndarray] = []
        for r in results:
            if not r["ok"]:
                continue
            v = np.asarray(r["embedding"], dtype=np.float32)
            if any(float(v @ k) > 0.995 for k in kept):
                r.update(ok=False, reason="near_duplicate_frame")
                r.pop("embedding", None)
            else:
                kept.append(v)
        return results
