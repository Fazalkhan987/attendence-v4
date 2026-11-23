"""Face detection (InsightFace SCRFD) + embedding (ArcFace) + quality gates (OpenCV)."""
import logging
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from face_engine.config import Config

log = logging.getLogger("face_engine.detection")


@dataclass
class DetectedFace:
    bbox: tuple[float, float, float, float]
    det_score: float
    kps: np.ndarray  # (5, 2)
    embedding: np.ndarray  # L2-normalised (512,)
    pose: tuple[float, float, float] | None  # pitch, yaw, roll (degrees) when available

    @property
    def size(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return min(x2 - x1, y2 - y1)


class FaceDetector:
    def __init__(self, cfg: Config):
        from insightface.app import FaceAnalysis  # imported lazily: heavy

        self.cfg = cfg
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if cfg.use_gpu else ["CPUExecutionProvider"]
        self.app = FaceAnalysis(name=cfg.model_name, providers=providers)
        self.app.prepare(ctx_id=0 if cfg.use_gpu else -1, det_size=(cfg.det_size, cfg.det_size))
        self._lock = threading.Lock()  # one inference at a time per process
        log.info("InsightFace model '%s' ready (gpu=%s)", cfg.model_name, cfg.use_gpu)

    def detect(self, frame_bgr: np.ndarray) -> list[DetectedFace]:
        with self._lock:
            faces = self.app.get(frame_bgr)
        out = []
        for f in faces:
            emb = getattr(f, "normed_embedding", None)
            if emb is None:
                continue
            pose = getattr(f, "pose", None)
            out.append(
                DetectedFace(
                    bbox=tuple(float(v) for v in f.bbox),
                    det_score=float(f.det_score),
                    kps=np.asarray(f.kps, dtype=np.float32),
                    embedding=np.asarray(emb, dtype=np.float32),
                    pose=tuple(float(p) for p in pose) if pose is not None else None,
                )
            )
        return out


def crop_face(frame: np.ndarray, bbox, margin: float = 0.1) -> np.ndarray:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    x1, y1, x2, y2 = max(0, int(x1 - mx)), max(0, int(y1 - my)), min(w, int(x2 + mx)), min(h, int(y2 + my))
    return frame[y1:y2, x1:x2]


def sharpness(frame: np.ndarray, bbox) -> float:
    """Variance of the Laplacian on the face crop (higher = sharper)."""
    crop = crop_face(frame, bbox)
    if crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(cv2.resize(crop, (112, 112)), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def quality_issues(face: DetectedFace, frame: np.ndarray, *, min_size: int, min_det: float, min_blur: float, max_yaw: float, max_pitch: float) -> tuple[list[str], float]:
    """Returns (problems, quality score 0..1). An empty problem list means the face is usable."""
    problems = []
    if face.det_score < min_det:
        problems.append("low_detection_confidence")
    if face.size < min_size:
        problems.append("face_too_small")
    blur = sharpness(frame, face.bbox)
    if blur < min_blur:
        problems.append("image_blurry")
    if face.pose is not None:
        pitch, yaw, _ = face.pose
        if abs(yaw) > max_yaw:
            problems.append("face_turned_too_far")
        elif abs(pitch) > max_pitch:
            problems.append("head_tilted_too_far")
    quality = face.det_score * min(1.0, blur / (3 * max(min_blur, 1.0)))
    return problems, float(quality)
