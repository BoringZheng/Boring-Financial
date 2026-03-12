from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Thread

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.models import ClassificationResult, ImportBatch, Transaction, UploadedFile
from backend.services.classifiers import classify_transaction
from backend.services.parsers import ParserRegistry, TransactionNormalizer
from backend.utils.normalizers import build_dedupe_hash

parser_registry = ParserRegistry()
TERMINAL_BATCH_STATUSES = {"done", "failed", "partial_failed"}


def classify_transaction_in_session(
    transaction_id: int,
    user_id: int,
    provider_override: str | None = None,
) -> str | None:
    db = SessionLocal()
    try:
        transaction = db.get(Transaction, transaction_id)
        if transaction is None or transaction.user_id != user_id:
            return "transaction not found"
        classify_transaction(
            db,
            transaction,
            user_id,
            provider_override=provider_override,
            auto_commit=True,
        )
        return None
    except Exception as exc:
        db.rollback()
        return str(exc)
    finally:
        db.close()


def _append_error_message(target: ImportBatch | UploadedFile, message: str) -> None:
    clean_message = message.strip()
    if not clean_message:
        return
    existing = (target.error_message or "").strip()
    if clean_message in existing:
        return
    combined = f"{existing}\n{clean_message}".strip() if existing else clean_message
    target.error_message = combined[:4000]


def create_import_batch(db: Session, user_id: int, files: list[tuple[str, bytes]]) -> ImportBatch:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    batch = ImportBatch(
        user_id=user_id,
        status="queued",
        source_count=len(files),
        total_count=0,
        processed_count=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    for filename, content in files:
        safe_name = Path(filename).name
        stored_path = settings.uploads_dir / f"user-{user_id}-batch-{batch.id}-{safe_name}"
        stored_path.write_bytes(content)
        uploaded = UploadedFile(batch_id=batch.id, filename=safe_name, stored_path=str(stored_path), status="queued")
        db.add(uploaded)
    db.commit()
    return batch


def start_import_batch(batch_id: int, provider_override: str | None = None) -> None:
    worker = Thread(
        target=run_import_batch,
        args=(batch_id, provider_override),
        daemon=True,
        name=f"import-batch-{batch_id}",
    )
    worker.start()


def run_import_batch(batch_id: int, provider_override: str | None = None) -> None:
    db = SessionLocal()
    try:
        process_import_batch(db, batch_id, provider_override=provider_override)
    except Exception as exc:
        batch = db.get(ImportBatch, batch_id)
        if batch is not None:
            batch.status = "failed"
            _append_error_message(batch, str(exc))
            db.commit()
    finally:
        db.close()


def process_import_batch(db: Session, batch_id: int, provider_override: str | None = None) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise ValueError("batch not found")

    batch.status = "processing"
    batch.error_message = None
    batch.total_count = 0
    batch.processed_count = 0
    db.commit()

    uploaded_files = db.scalars(select(UploadedFile).where(UploadedFile.batch_id == batch.id)).all()
    has_failures = False
    progress_since_commit = 0

    max_workers = max(1, settings.import_classification_workers)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bill-classify") as executor:
        for uploaded in uploaded_files:
            uploaded.status = "processing"
            uploaded.error_message = None
            db.commit()

            try:
                parsed_transactions = parser_registry.parse_file(uploaded.stored_path)
                batch.total_count += len(parsed_transactions)
                uploaded.platform = parsed_transactions[0].platform if parsed_transactions else None
                db.commit()

                file_has_failures = False
                pending_futures: list[Future[str | None]] = []
                for parsed in parsed_transactions:
                    try:
                        normalized = TransactionNormalizer.normalize_text_fields(parsed)
                        dedupe_hash = build_dedupe_hash(
                            parsed.platform,
                            parsed.occurred_at,
                            parsed.amount,
                            parsed.merchant,
                            parsed.item,
                        )
                        duplicate = db.scalar(
                            select(Transaction).where(
                                Transaction.user_id == batch.user_id,
                                Transaction.dedupe_hash == dedupe_hash,
                            )
                        )
                        if duplicate is None:
                            transaction = Transaction(
                                user_id=batch.user_id,
                                batch_id=batch.id,
                                uploaded_file_id=uploaded.id,
                                platform=parsed.platform,
                                occurred_at=parsed.occurred_at,
                                type=parsed.type,
                                amount=parsed.amount,
                                merchant=str(parsed.merchant or "")[:255],
                                item=str(parsed.item or "")[:255],
                                method=str(parsed.method or "")[:128],
                                status=str(parsed.status or "")[:128],
                                note=str(parsed.note or ""),
                                dedupe_hash=dedupe_hash,
                                **normalized,
                            )
                            db.add(transaction)
                            db.commit()
                            pending_futures.append(
                                executor.submit(
                                    classify_transaction_in_session,
                                    transaction.id,
                                    batch.user_id,
                                    provider_override,
                                )
                            )
                        else:
                            batch.processed_count += 1
                            progress_since_commit += 1
                            if progress_since_commit >= settings.import_progress_commit_interval:
                                db.commit()
                                progress_since_commit = 0
                    except Exception as exc:
                        db.rollback()
                        file_has_failures = True
                        batch.processed_count += 1
                        progress_since_commit += 1
                        _append_error_message(uploaded, str(exc))
                        _append_error_message(batch, f"{uploaded.filename}: {exc}")
                        db.commit()
                        progress_since_commit = 0

                for future in as_completed(pending_futures):
                    error_message = future.result()
                    if error_message:
                        file_has_failures = True
                        _append_error_message(uploaded, error_message)
                        _append_error_message(batch, f"{uploaded.filename}: {error_message}")
                    batch.processed_count += 1
                    progress_since_commit += 1
                    if progress_since_commit >= settings.import_progress_commit_interval:
                        db.commit()
                        progress_since_commit = 0

                if file_has_failures:
                    has_failures = True
                    uploaded.status = "partial_failed"
                else:
                    uploaded.status = "done"
                db.commit()
                progress_since_commit = 0
            except Exception as exc:
                db.rollback()
                has_failures = True
                uploaded.status = "failed"
                _append_error_message(uploaded, str(exc))
                _append_error_message(batch, f"{uploaded.filename}: {exc}")
                db.commit()

    if has_failures:
        batch.status = "partial_failed"
    elif uploaded_files:
        batch.status = "done"
    else:
        batch.status = "failed"
        _append_error_message(batch, "no uploaded files found")

    db.commit()
    db.refresh(batch)
    return batch


def list_import_batches(db: Session, user_id: int) -> list[ImportBatch]:
    return db.scalars(
        select(ImportBatch).where(ImportBatch.user_id == user_id).order_by(ImportBatch.created_at.desc())
    ).all()


def list_uploaded_files(db: Session, user_id: int) -> list[UploadedFile]:
    return db.scalars(
        select(UploadedFile)
        .join(ImportBatch, UploadedFile.batch_id == ImportBatch.id)
        .where(ImportBatch.user_id == user_id)
        .order_by(UploadedFile.created_at.desc(), UploadedFile.id.desc())
    ).all()


def delete_import_batch(db: Session, batch_id: int, user_id: int) -> None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.user_id != user_id:
        raise ValueError("batch not found")

    uploaded_files = db.scalars(select(UploadedFile).where(UploadedFile.batch_id == batch_id)).all()
    transaction_ids = db.scalars(select(Transaction.id).where(Transaction.batch_id == batch_id)).all()

    if transaction_ids:
        db.execute(delete(ClassificationResult).where(ClassificationResult.transaction_id.in_(transaction_ids)))
        db.execute(delete(Transaction).where(Transaction.id.in_(transaction_ids)))

    if uploaded_files:
        db.execute(delete(UploadedFile).where(UploadedFile.batch_id == batch_id))

    db.delete(batch)
    db.commit()

    for uploaded_file in uploaded_files:
        try:
            Path(uploaded_file.stored_path).unlink(missing_ok=True)
        except Exception:
            pass
