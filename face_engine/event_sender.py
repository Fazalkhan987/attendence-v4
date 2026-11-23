"""Talks to the backend over REST: pulls the embedding gallery and posts *confirmed* recognition events.

Only the minimum is sent: employee code, camera code, confidence, timestamp (+ a unique event id for replay
protection). No video frames, names, departments, schedules or attendance statuses ever leave this process.
"""
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone

import requests

from face_engine.config import Config

log = logging.getLogger("face_engine.sender")


class BackendClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({"X-Camera-Code": cfg.camera_code, "X-Camera-Key": cfg.camera_key})
        self.base = f"{cfg.backend_url}/api/v1/recognition"

    def fetch_gallery(self, since_version: str | None = None) -> dict:
        r = self.session.get(f"{self.base}/gallery", params={"since_version": since_version} if since_version else None, timeout=20)
        r.raise_for_status()
        return r.json()

    def post_event(self, payload: dict) -> requests.Response:
        return self.session.post(f"{self.base}/events", json=payload, timeout=10)


class EventSender:
    """Background queue with retry/backoff so a short backend outage does not lose confirmed events."""

    def __init__(self, cfg: Config, client: BackendClient):
        self.cfg = cfg
        self.client = client
        self.q: queue.Queue[dict] = queue.Queue(maxsize=500)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="event-sender")

    def start(self) -> "EventSender":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def submit(self, employee_code: str, confidence: float, when: datetime | None = None) -> None:
        when = when or datetime.now(timezone.utc)
        payload = {
            "employee_id": employee_code,
            "camera_id": self.cfg.camera_code,
            "confidence": round(float(confidence), 4),
            "timestamp": when.isoformat(),
            "event_id": str(uuid.uuid4()),
        }
        try:
            self.q.put_nowait(payload)
        except queue.Full:
            log.error("Event queue full, dropping event for %s", employee_code)

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._deliver(payload)

    def _deliver(self, payload: dict) -> None:
        delay = 1.0
        created = datetime.fromisoformat(payload["timestamp"])
        while not self._stop.is_set():
            age = (datetime.now(timezone.utc) - created).total_seconds()
            if age > self.cfg.event_max_age_seconds:
                log.error("Dropping event %s: older than %ss (backend would reject it)", payload["event_id"], self.cfg.event_max_age_seconds)
                return
            try:
                r = self.client.post_event(payload)
                if r.status_code == 200:
                    body = r.json()
                    log.info("EVENT %s -> %s %s %s", payload["employee_id"], body.get("outcome"), body.get("action") or "", body.get("reason") or "")
                    return
                if r.status_code in (400, 401, 403, 404, 422):
                    log.error("Backend refused event (%s): %s", r.status_code, r.text[:200])
                    return
                log.warning("Backend returned %s, retrying", r.status_code)
            except requests.RequestException as exc:
                log.warning("Backend unreachable (%s), retrying in %.0fs", exc.__class__.__name__, delay)
            time.sleep(delay)
            delay = min(delay * 2, 15.0)
