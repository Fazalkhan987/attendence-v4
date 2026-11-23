import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Config:
    # backend connection
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    camera_code: str = os.getenv("CAMERA_CODE", "CAM-01")
    camera_key: str = os.getenv("CAMERA_KEY", "")
    event_max_age_seconds: int = _i("EVENT_MAX_AGE_SECONDS", 240)

    # video
    video_source: str = os.getenv("VIDEO_SOURCE", "0")
    show_preview: bool = _b("SHOW_PREVIEW", True)
    process_every_n_frames: int = _i("PROCESS_EVERY_N_FRAMES", 2)

    # enrollment service
    service_host: str = os.getenv("SERVICE_HOST", "127.0.0.1")
    service_port: int = _i("SERVICE_PORT", 8100)
    service_key: str = os.getenv("SERVICE_KEY", "change-me")

    # model
    model_name: str = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
    use_gpu: bool = _b("USE_GPU", False)
    det_size: int = _i("DET_SIZE", 640)

    # recognition
    similarity_threshold: float = _f("SIMILARITY_THRESHOLD", 0.50)
    match_margin: float = _f("MATCH_MARGIN", 0.05)
    confirm_frames: int = _i("CONFIRM_FRAMES", 5)
    confirm_window_seconds: float = _f("CONFIRM_WINDOW_SECONDS", 4.0)
    event_cooldown_seconds: int = _i("EVENT_COOLDOWN_SECONDS", 120)
    gallery_refresh_seconds: int = _i("GALLERY_REFRESH_SECONDS", 60)
    track_ttl_seconds: float = _f("TRACK_TTL_SECONDS", 2.0)

    # quality gates
    min_face_size: int = _i("MIN_FACE_SIZE", 80)
    min_det_score: float = _f("MIN_DET_SCORE", 0.60)
    min_blur: float = _f("MIN_BLUR", 25.0)
    max_yaw: float = _f("MAX_YAW", 40.0)
    max_pitch: float = _f("MAX_PITCH", 35.0)

    # enrollment is stricter than live recognition
    enroll_min_face_size: int = _i("ENROLL_MIN_FACE_SIZE", 110)
    enroll_min_det_score: float = _f("ENROLL_MIN_DET_SCORE", 0.75)
    enroll_min_blur: float = _f("ENROLL_MIN_BLUR", 40.0)
    enroll_max_yaw: float = _f("ENROLL_MAX_YAW", 30.0)
    enroll_max_pitch: float = _f("ENROLL_MAX_PITCH", 25.0)

    # presentation attack heuristics
    liveness_enabled: bool = _b("LIVENESS_ENABLED", True)
    liveness_min_texture: float = _f("LIVENESS_MIN_TEXTURE", 20.0)
    liveness_min_motion: float = _f("LIVENESS_MIN_MOTION", 0.003)


def load_config() -> Config:
    return Config()
