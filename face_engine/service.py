"""Small internal HTTP service used by the backend during enrollment.

    python -m face_engine.service

Only the backend may call it (X-Service-Key). The browser never talks to this service.
"""
import base64
import hmac
import logging

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from face_engine.config import load_config
from face_engine.detection import FaceDetector
from face_engine.registration import EnrollmentProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
cfg = load_config()
app = FastAPI(title="Face Engine Service")
_processor: EnrollmentProcessor | None = None


def processor() -> EnrollmentProcessor:
    global _processor
    if _processor is None:
        _processor = EnrollmentProcessor(FaceDetector(cfg), cfg)
    return _processor


def require_key(x_service_key: str = Header(..., alias="X-Service-Key")) -> None:
    if not hmac.compare_digest(x_service_key, cfg.service_key):
        raise HTTPException(401, "Invalid service key")


class EmbedRequest(BaseModel):
    images: list[str] = Field(min_length=1, max_length=20)


@app.on_event("startup")
def _warm_up() -> None:
    processor()  # load the model once at startup


@app.get("/health")
def health():
    return {"status": "ok", "model": cfg.model_name}


@app.post("/v1/embed", dependencies=[Depends(require_key)])
def embed(body: EmbedRequest):
    raw = []
    for b in body.images:
        try:
            raw.append(base64.b64decode(b))
        except Exception:
            raw.append(b"")
    return {"results": processor().process(raw)}


if __name__ == "__main__":
    uvicorn.run(app, host=cfg.service_host, port=cfg.service_port)
