from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import settings
from backend.db.base import Base
from backend.db.runtime_schema import ensure_runtime_schema
from backend.db.session import engine, SessionLocal
from backend.services.bootstrap import seed_defaults


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()

    # Migrate existing timeout transactions into the retry queue
    from backend.services.retry_queue import migrate_existing_timeouts, run_retry_queue_worker
    migrate_existing_timeouts()

    # Start background retry worker
    stop_event = threading.Event()
    worker = threading.Thread(
        target=run_retry_queue_worker,
        args=(stop_event,),
        daemon=True,
        name="retry-queue-worker",
    )
    worker.start()

    yield

    # Shutdown
    stop_event.set()
    worker.join(timeout=5)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
