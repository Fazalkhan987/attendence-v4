import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete

from app.api.router import api_router
from app.core.config import settings
from app.database import SessionLocal, engine
from app.models import Base, RecognitionEvent
from app.seed import ensure_leave_types
from app.services.attendance_service import finalize_attendance
from app.utils.timeutils import now_utc

log = logging.getLogger("attendance")


def _finalize_job() -> None:
    with SessionLocal() as db:
        stats = finalize_attendance(db)
        if any(stats.values()):
            log.info("finalizer: %s", stats)


def _retention_job() -> None:
    cutoff = now_utc() - timedelta(days=settings.RECOGNITION_RETENTION_DAYS)
    with SessionLocal() as db:
        db.execute(delete(RecognitionEvent).where(RecognitionEvent.event_timestamp < cutoff))
        db.commit()


async def _background_loop() -> None:
    ticks = 0
    per_day = max(1, int(86400 / settings.FINALIZER_INTERVAL_SECONDS))
    while True:
        try:
            await run_in_threadpool(_finalize_job)
            if ticks % per_day == 0:
                await run_in_threadpool(_retention_job)
        except Exception:  # keep the loop alive
            log.exception("background job failed")
        ticks += 1
        await asyncio.sleep(settings.FINALIZER_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            ensure_leave_types(db)
    task = asyncio.create_task(_background_loop()) if settings.ENABLE_BACKGROUND_JOBS else None
    yield
    if task:
        task.cancel()


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "time": now_utc().isoformat()}
