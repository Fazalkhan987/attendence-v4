"""Threaded video capture for webcams and RTSP/HTTP CCTV streams (always keeps the *latest* frame)."""
import logging
import threading
import time

import cv2

log = logging.getLogger("face_engine.camera")


class CameraStream:
    def __init__(self, source: str | int, reconnect_delay: float = 3.0):
        self.source = int(source) if str(source).isdigit() else source
        self.reconnect_delay = reconnect_delay
        self._cap: cv2.VideoCapture | None = None
        self._frame = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="camera-reader")

    def start(self) -> "CameraStream":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        if self._cap is not None:
            self._cap.release()

    def _open(self) -> bool:
        if self._cap is not None:
            self._cap.release()
        self._cap = cv2.VideoCapture(self.source)
        if isinstance(self.source, int):
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return self._cap.isOpened()

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                if not self._open():
                    log.warning("Cannot open video source %r, retrying in %.0fs", self.source, self.reconnect_delay)
                    time.sleep(self.reconnect_delay)
                    continue
                log.info("Video source %r opened", self.source)
            ok, frame = self._cap.read()
            if not ok:
                log.warning("Frame grab failed, reconnecting")
                self._cap.release()
                self._cap = None
                time.sleep(self.reconnect_delay)
                continue
            with self._lock:
                self._frame = frame
                self._frame_id += 1

    def read(self, last_id: int = -1):
        """Returns (frame_id, frame) of the newest frame, or (last_id, None) if nothing new."""
        with self._lock:
            if self._frame is None or self._frame_id == last_id:
                return last_id, None
            return self._frame_id, self._frame.copy()
