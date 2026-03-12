from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from backend.api.router import api_router
from backend.core.config import settings
from backend.db.base import Base
from backend.db.session import engine, SessionLocal
from backend.services.bootstrap import seed_defaults


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if "import_batches" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("import_batches")}
    statements: list[str] = []
    if "total_count" not in columns:
        statements.append("ALTER TABLE import_batches ADD COLUMN total_count INTEGER DEFAULT 0 NOT NULL")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
    yield


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
