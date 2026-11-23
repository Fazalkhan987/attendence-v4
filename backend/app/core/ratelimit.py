"""Tiny in-memory login throttle (per process). Use Redis for multi-worker deployments."""
import threading
import time

from app.core.config import settings

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}


def _prune(key: str, now: float) -> list[float]:
    window = settings.LOGIN_LOCK_MINUTES * 60
    items = [t for t in _failures.get(key, []) if now - t < window]
    _failures[key] = items
    return items


def is_locked(key: str) -> bool:
    with _lock:
        return len(_prune(key, time.time())) >= settings.LOGIN_MAX_FAILURES


def register_failure(key: str) -> None:
    with _lock:
        now = time.time()
        _prune(key, now).append(now)


def reset(key: str) -> None:
    with _lock:
        _failures.pop(key, None)
