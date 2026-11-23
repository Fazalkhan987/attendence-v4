"""Matching, multi-frame identity confirmation and duplicate suppression."""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from face_engine.config import Config
from face_engine.detection import DetectedFace
from face_engine.event_sender import BackendClient
from face_engine.liveness import LivenessChecker, LivenessState

log = logging.getLogger("face_engine.recognition")


# ----------------------------------------------------------------------------
class Gallery:
    """In-memory copy of registered employee embeddings, refreshed from the backend."""

    def __init__(self, cfg: Config, client: BackendClient):
        self.cfg = cfg
        self.client = client
        self.version: str | None = None
        self._matrix = np.zeros((0, 512), dtype=np.float32)
        self._labels: list[str] = []
        self._groups: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()
        self._last_refresh = 0.0

    def refresh(self, force: bool = False) -> bool:
        if not force and time.time() - self._last_refresh < self.cfg.gallery_refresh_seconds:
            return False
        self._last_refresh = time.time()
        try:
            data = self.client.fetch_gallery(None if force else self.version)
        except Exception as exc:  # network / auth problems: keep the current gallery
            log.warning("Gallery refresh failed: %s", exc)
            return False
        if data.get("unchanged"):
            return False
        vecs, labels = [], []
        for emp in data["employees"]:
            for e in emp["embeddings"]:
                v = np.asarray(e, dtype=np.float32)
                vecs.append(v / (np.linalg.norm(v) + 1e-9))
                labels.append(emp["employee_id"])
        matrix = np.stack(vecs) if vecs else np.zeros((0, 512), dtype=np.float32)
        groups = {c: np.where(np.array(labels) == c)[0] for c in set(labels)}
        with self._lock:
            self._matrix, self._labels, self._groups, self.version = matrix, labels, groups, data["version"]
        log.info("Gallery loaded: %d employees, %d embeddings (version %s)", len(groups), len(labels), self.version)
        return True

    def match(self, emb: np.ndarray) -> tuple[str | None, float]:
        """Returns (employee_code or None, similarity). Unknown / ambiguous faces return None."""
        with self._lock:
            if len(self._labels) == 0:
                return None, 0.0
            sims = self._matrix @ emb
            per_emp = {code: float(sims[idx].max()) for code, idx in self._groups.items()}
        ranked = sorted(per_emp.items(), key=lambda kv: kv[1], reverse=True)
        best_code, best = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else -1.0
        if best < self.cfg.similarity_threshold:
            return None, best
        if best - second < self.cfg.match_margin:  # two employees look alike => do not guess
            return None, best
        return best_code, best


# ----------------------------------------------------------------------------
def _iou(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    bbox: tuple
    last_seen: float
    first_seen: float
    obs: deque = field(default_factory=lambda: deque(maxlen=30))  # (time, code|None, sim)
    live: LivenessState = field(default_factory=LivenessState)
    emitted: bool = False


@dataclass
class ConfirmedMatch:
    employee_code: str
    confidence: float
    track_id: int


class IdentityConfirmer:
    """Tracks faces between frames and only confirms an identity after N consistent observations."""

    def __init__(self, cfg: Config, liveness: LivenessChecker):
        self.cfg = cfg
        self.liveness = liveness
        self.tracks: dict[int, Track] = {}
        self._next_id = 1
        self._last_emitted: dict[str, float] = {}

    def _associate(self, bbox, now: float) -> Track:
        best, best_iou = None, 0.3
        for t in self.tracks.values():
            iou = _iou(bbox, t.bbox)
            if iou > best_iou:
                best, best_iou = t, iou
        if best is None:
            best = Track(id=self._next_id, bbox=bbox, last_seen=now, first_seen=now)
            self._next_id += 1
            self.tracks[best.id] = best
        best.bbox, best.last_seen = bbox, now
        return best

    def update(self, observations: list[tuple[DetectedFace, str | None, float]], frame: np.ndarray) -> list[ConfirmedMatch]:
        now = time.time()
        confirmed: list[ConfirmedMatch] = []
        for face, code, sim in observations:
            tr = self._associate(face.bbox, now)
            tr.obs.append((now, code, sim))
            self.liveness.update(tr.live, face, frame)
            m = self._check(tr, now)
            if m:
                confirmed.append(m)
        for tid in [t.id for t in self.tracks.values() if now - t.last_seen > self.cfg.track_ttl_seconds]:
            del self.tracks[tid]
        return confirmed

    def _check(self, tr: Track, now: float) -> ConfirmedMatch | None:
        n = self.cfg.confirm_frames
        if tr.emitted or len(tr.obs) < n:
            return None
        recent = list(tr.obs)[-n:]
        codes = {c for _, c, _ in recent}
        if len(codes) != 1 or None in codes:
            return None
        if recent[-1][0] - recent[0][0] > self.cfg.confirm_window_seconds:
            return None
        code = next(iter(codes))
        mean_sim = float(np.mean([s for _, _, s in recent]))
        if mean_sim < self.cfg.similarity_threshold:
            return None
        if now - self._last_emitted.get(code, 0.0) < self.cfg.event_cooldown_seconds:
            tr.emitted = True  # same person still standing there; stay quiet
            return None
        if not self.liveness.is_live(tr.live):
            return None  # keep observing; a real face will start moving
        tr.emitted = True
        self._last_emitted[code] = now
        return ConfirmedMatch(employee_code=code, confidence=mean_sim, track_id=tr.id)
