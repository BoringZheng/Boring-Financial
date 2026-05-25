from __future__ import annotations

import logging
import threading
from typing import Callable

from sqlalchemy import func, select

from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.models import Transaction
from backend.services.classifiers import (
    DEFAULT_EXTERNAL_PROVIDER,
    RETRY_FAILED_PROVIDER,
    RETRY_QUEUE_PROVIDER,
    classify_transaction,
)

logger = logging.getLogger(__name__)


def _retry_one(db, txn: Transaction) -> None:
    """Classify a single transaction. Errors and requeueing are handled
    inside classify_transaction -> CompositeClassifier.classify."""
    provider = txn.api_retry_provider or DEFAULT_EXTERNAL_PROVIDER
    classify_transaction(
        db, txn, txn.user_id,
        provider_override=provider,
        auto_commit=True,
        force_refresh=True,
        enqueue_external=False,
    )


def run_retry_queue_worker(stop_event: threading.Event) -> None:
    """Background daemon: poll the retry_queue table and retry one tx at a time.

    Transactions with ``auto_provider == "retry_queue"`` are picked up in
    FIFO order (ordered by api_retry_count ASC so earlier failures get
    priority).  After each attempt the worker sleeps **delay_seconds**
    to rate-limit requests to the external API.  When the queue is empty
    it sleeps **poll_seconds** before checking again.
    """
    logger.info(
        "Retry queue worker started (max_retries=%d, delay=%.1fs, poll=%.1fs)",
        settings.retry_queue_max_retries,
        settings.retry_queue_delay_seconds,
        settings.retry_queue_poll_seconds,
    )

    while not stop_event.is_set():
        db = SessionLocal()
        try:
            txn = db.scalars(
                select(Transaction)
                .where(Transaction.auto_provider == RETRY_QUEUE_PROVIDER)
                .order_by(Transaction.updated_at.asc(), Transaction.created_at.asc(), Transaction.id.asc())
                .limit(1)
            ).first()

            if txn is None:
                stop_event.wait(settings.retry_queue_poll_seconds)
                continue

            logger.info(
                "Retrying transaction %d (attempt %d/%d)",
                txn.id,
                txn.api_retry_count + 1,
                settings.retry_queue_max_retries,
            )
            _retry_one(db, txn)

        except Exception as exc:
            logger.error("Retry worker error: %s", exc)
        finally:
            db.close()

        # Rate-limit between requests so the external API is not flooded
        stop_event.wait(settings.retry_queue_delay_seconds)

    logger.info("Retry queue worker stopped")


def migrate_existing_timeouts() -> int:
    """One-shot: move existing timeout transactions into the retry queue.

    Finds old transactions where ``needs_review`` is True, ``auto_reason``
    contains ``"external api"``, and the retry budget has not been exhausted.
    Sets ``auto_provider = "retry_queue"``, ``needs_review = False``,
    and ``api_retry_count = 0`` so the background worker picks them up.
    """
    db = SessionLocal()
    try:
        txns = db.scalars(
            select(Transaction).where(
                Transaction.needs_review == True,
                Transaction.auto_reason.contains("external api"),
                Transaction.api_retry_count < settings.retry_queue_max_retries,
            )
        ).all()

        if not txns:
            return 0

        for txn in txns:
            txn.auto_provider = "retry_queue"
            txn.needs_review = False
            txn.api_retry_count = 0
            txn.api_retry_provider = DEFAULT_EXTERNAL_PROVIDER
            txn.api_retry_last_error = None

        db.commit()
        logger.info("Migrated %d existing timeout transactions to retry queue", len(txns))
        return len(txns)
    finally:
        db.close()


def requeue_all_external_api_failures(
    user_id: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Admin action: push ALL transactions with external-api issues back into
    the retry queue, regardless of their current status.

    If *on_progress* is provided it is called as ``on_progress(current, total)``
    after each transaction is updated.

    Returns the number of transactions queued.
    """
    db = SessionLocal()
    try:
        query = select(Transaction).where(
            (Transaction.auto_provider == RETRY_QUEUE_PROVIDER)
            | (Transaction.auto_provider == RETRY_FAILED_PROVIDER)
            | (Transaction.auto_reason.contains("external api"))
        )
        if user_id is not None:
            query = query.where(Transaction.user_id == user_id)
        txns = db.scalars(query).all()

        if not txns:
            logger.info("No transactions with external API issues found")
            return 0

        total = len(txns)
        for i, txn in enumerate(txns):
            txn.auto_provider = "retry_queue"
            txn.needs_review = False
            txn.api_retry_count = 0
            txn.api_retry_provider = txn.api_retry_provider or DEFAULT_EXTERNAL_PROVIDER
            txn.api_retry_last_error = None
            if on_progress is not None:
                on_progress(i + 1, total)

        db.commit()
        logger.info("Requeued %d transactions into retry queue", total)
        return total
    finally:
        db.close()


def _isoformat(value) -> str | None:
    return value.isoformat() if value is not None else None


def get_retry_queue_status(user_id: int | None = None) -> dict:
    """Return aggregate retry queue status for admin dashboards.

    The response intentionally avoids transaction-level details, merchant text,
    notes, and raw provider errors.
    """
    db = SessionLocal()
    try:
        base_filters = [Transaction.auto_provider.in_([RETRY_QUEUE_PROVIDER, RETRY_FAILED_PROVIDER])]
        if user_id is not None:
            base_filters.append(Transaction.user_id == user_id)

        counts = dict(
            db.execute(
                select(Transaction.auto_provider, func.count())
                .where(*base_filters)
                .group_by(Transaction.auto_provider)
            ).all()
        )
        queued = int(counts.get(RETRY_QUEUE_PROVIDER, 0))
        failed = int(counts.get(RETRY_FAILED_PROVIDER, 0))

        provider_rows = db.execute(
            select(
                Transaction.api_retry_provider,
                Transaction.auto_provider,
                func.count(),
            )
            .where(*base_filters)
            .group_by(Transaction.api_retry_provider, Transaction.auto_provider)
        ).all()
        providers: dict[str, dict[str, int | str]] = {}
        for provider, status, count in provider_rows:
            provider_name = provider or DEFAULT_EXTERNAL_PROVIDER
            entry = providers.setdefault(provider_name, {"provider": provider_name, "queued": 0, "failed": 0})
            if status == RETRY_QUEUE_PROVIDER:
                entry["queued"] = int(count)
            elif status == RETRY_FAILED_PROVIDER:
                entry["failed"] = int(count)

        retry_count_rows = db.execute(
            select(Transaction.api_retry_count, func.count())
            .where(Transaction.auto_provider == RETRY_QUEUE_PROVIDER, *(base_filters[1:]))
            .group_by(Transaction.api_retry_count)
            .order_by(Transaction.api_retry_count.asc())
        ).all()

        oldest_queued = db.scalar(
            select(func.min(Transaction.updated_at)).where(
                Transaction.auto_provider == RETRY_QUEUE_PROVIDER,
                *(base_filters[1:]),
            )
        )
        oldest_failed = db.scalar(
            select(func.min(Transaction.updated_at)).where(
                Transaction.auto_provider == RETRY_FAILED_PROVIDER,
                *(base_filters[1:]),
            )
        )
        newest_activity = db.scalar(select(func.max(Transaction.updated_at)).where(*base_filters))

        return {
            "queued": queued,
            "failed": failed,
            "total": queued + failed,
            "max_retries": settings.retry_queue_max_retries,
            "delay_seconds": settings.retry_queue_delay_seconds,
            "poll_seconds": settings.retry_queue_poll_seconds,
            "oldest_queued_at": _isoformat(oldest_queued),
            "oldest_failed_at": _isoformat(oldest_failed),
            "newest_activity_at": _isoformat(newest_activity),
            "providers": sorted(providers.values(), key=lambda item: str(item["provider"])),
            "retry_counts": [
                {"retry_count": int(retry_count or 0), "queued": int(count)}
                for retry_count, count in retry_count_rows
            ],
        }
    finally:
        db.close()
