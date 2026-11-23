"""Lightweight passive presentation-attack (spoof) heuristics.

What this does:
  * texture check  - very smooth/flat crops (low Laplacian variance) are typical of low-quality screens/prints
  * micro-motion   - a live face shows small landmark-geometry changes (breathing, blinks, expression) over several
                     frames; a rigid photo held in front of the camera keeps the *relative* landmark layout constant.
Together with multi-frame identity confirmation these stop casual attacks (a phone photo, a printout).

What this does NOT do: it is not a trained anti-spoofing model, so it will not stop good video replays, masks or
deepfakes. For a production deployment add a passive anti-spoof network (e.g. MiniFASNet) or IR/depth hardware by
implementing `is_live()` in this class. Set LIVENESS_ENABLED=false to disable the heuristics.
"""
from collections import deque

import numpy as np

from face_engine.config import Config
from face_engine.detection import DetectedFace, crop_face

import cv2


def _relative_landmarks(kps: np.ndarray) -> np.ndarray:
    eyes_center = (kps[0] + kps[1]) / 2.0
    scale = np.linalg.norm(kps[0] - kps[1]) + 1e-6
    return (kps - eyes_center) / scale


class LivenessState:
    """Per-track rolling history."""

    def __init__(self, maxlen: int = 12):
        self.geometry: deque[np.ndarray] = deque(maxlen=maxlen)
        self.texture: deque[float] = deque(maxlen=maxlen)


class LivenessChecker:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def update(self, state: LivenessState, face: DetectedFace, frame: np.ndarray) -> None:
        state.geometry.append(_relative_landmarks(face.kps))
        crop = crop_face(frame, face.bbox)
        if crop.size:
            gray = cv2.cvtColor(cv2.resize(crop, (96, 96)), cv2.COLOR_BGR2GRAY)
            state.texture.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))

    def is_live(self, state: LivenessState) -> bool:
        if not self.cfg.liveness_enabled:
            return True
        if len(state.geometry) < max(3, self.cfg.confirm_frames):
            return False
        if state.texture and float(np.mean(state.texture)) < self.cfg.liveness_min_texture:
            return False
        motion = float(np.mean(np.std(np.stack(state.geometry), axis=0)))
        return motion >= self.cfg.liveness_min_motion
