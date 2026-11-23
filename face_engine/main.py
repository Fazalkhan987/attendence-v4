"""Live recognition loop.

    python -m face_engine.main

Captures frames, detects faces, matches them against the gallery pulled from the backend, confirms identities
over several frames and sends *only confirmed* recognition events to the backend. It never creates or edits
attendance records itself.
"""
import logging
import signal
import time

import cv2

from face_engine.camera import CameraStream
from face_engine.config import load_config
from face_engine.detection import FaceDetector, quality_issues
from face_engine.event_sender import BackendClient, EventSender
from face_engine.liveness import LivenessChecker
from face_engine.recognition import Gallery, IdentityConfirmer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("face_engine")


def main() -> None:
    cfg = load_config()
    if not cfg.camera_key or cfg.camera_key.startswith("paste-"):
        raise SystemExit("Set CAMERA_KEY in face_engine/.env (the key is shown once when the camera is created).")

    client = BackendClient(cfg)
    gallery = Gallery(cfg, client)
    gallery.refresh(force=True)
    detector = FaceDetector(cfg)
    confirmer = IdentityConfirmer(cfg, LivenessChecker(cfg))
    sender = EventSender(cfg, client).start()
    camera = CameraStream(cfg.video_source).start()

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("Recognition started on %s (source=%s)", cfg.camera_code, cfg.video_source)
    last_id, counter = -1, 0
    labels: list[tuple[tuple, str, float]] = []
    while running:
        last_id, frame = camera.read(last_id)
        if frame is None:
            time.sleep(0.01)
            continue
        counter += 1
        gallery.refresh()
        if counter % cfg.process_every_n_frames == 0:
            observations = []
            labels = []
            for face in detector.detect(frame):
                problems, _ = quality_issues(
                    face, frame, min_size=cfg.min_face_size, min_det=cfg.min_det_score,
                    min_blur=cfg.min_blur, max_yaw=cfg.max_yaw, max_pitch=cfg.max_pitch,
                )
                if problems:
                    labels.append((face.bbox, f"({problems[0]})", 0.0))
                    continue
                code, sim = gallery.match(face.embedding)  # unknown faces => code None => ignored
                observations.append((face, code, sim))
                labels.append((face.bbox, code or "unknown", sim))
            for m in confirmer.update(observations, frame):
                log.info("Confirmed %s (confidence %.2f)", m.employee_code, m.confidence)
                sender.submit(m.employee_code, m.confidence)

        if cfg.show_preview:
            for bbox, text, sim in labels:
                x1, y1, x2, y2 = map(int, bbox)
                color = (0, 200, 0) if text not in ("unknown",) and not text.startswith("(") else (0, 0, 220)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{text} {sim:.2f}" if sim else text, (x1, max(15, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.imshow(f"Face engine - {cfg.camera_code} (q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                running = False

    camera.stop()
    sender.stop()
    cv2.destroyAllWindows()
    log.info("Stopped")


if __name__ == "__main__":
    main()
