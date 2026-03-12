from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ImportBatchRead(BaseModel):
    id: int
    user_id: int
    status: str
    source_count: int
    total_count: int
    processed_count: int
    progress_percent: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadedFileRead(BaseModel):
    id: int
    batch_id: int
    filename: str
    platform: str | None
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    batch: ImportBatchRead
    message: str
