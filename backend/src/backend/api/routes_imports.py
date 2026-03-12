from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import ImportBatch, User
from backend.schemas.imports import ImportBatchRead, UploadResponse, UploadedFileRead
from backend.services.imports import (
    create_import_batch,
    delete_import_batch,
    list_import_batches,
    list_uploaded_files,
    start_import_batch,
)

router = APIRouter()


@router.get("", response_model=list[ImportBatchRead])
def get_import_batches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ImportBatchRead]:
    batches = list_import_batches(db, current_user.id)
    return [ImportBatchRead.model_validate(batch) for batch in batches]


@router.get("/files", response_model=list[UploadedFileRead])
def get_uploaded_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[UploadedFileRead]:
    files = list_uploaded_files(db, current_user.id)
    return [UploadedFileRead.model_validate(file) for file in files]


@router.post("", response_model=UploadResponse)
async def upload_bills(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UploadResponse:
    payloads = [(file.filename or "statement.csv", await file.read()) for file in files]
    batch = create_import_batch(db, current_user.id, payloads)
    start_import_batch(batch.id)
    db.refresh(batch)
    return UploadResponse(batch=ImportBatchRead.model_validate(batch), message="import started")


@router.get("/{batch_id}", response_model=ImportBatchRead)
def get_import_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ImportBatchRead:
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="batch not found")
    return ImportBatchRead.model_validate(batch)


@router.delete("/{batch_id}", status_code=204)
def remove_import_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        delete_import_batch(db, batch_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
