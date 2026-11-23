from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

UTC = timezone.utc
LOCAL_TZ = ZoneInfo(settings.TIMEZONE)


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Naive datetimes are interpreted as local (company) time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ)


def local_date(dt: datetime) -> date:
    return to_local(dt).date()


def at_local(d: date, t: time) -> datetime:
    """UTC datetime for local date `d` at local clock time `t`."""
    return datetime.combine(d, t.replace(tzinfo=None), tzinfo=LOCAL_TZ).astimezone(UTC)


def minutes_between(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)
