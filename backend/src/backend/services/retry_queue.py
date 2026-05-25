from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from sqlalchemy import select

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
                # Queue is empty — check for retry_failed txns to auto-requeue
                requeued = auto_requeue_failed()
                if requeued > 0:
                    continue  # immediately pick up the newly requeued txns
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


def auto_requeue_failed() -> int:
    """Periodic scan: move retry_failed transactions back to the retry queue
    after they have been sitting for *retry_queue_auto_requeue_minutes*.
    Resets api_retry_count so they get a fresh round of attempts."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.retry_queue_auto_requeue_minutes)
    db = SessionLocal()
    try:
        txns = db.scalars(
            select(Transaction).where(
                Transaction.auto_provider == RETRY_FAILED_PROVIDER,
                Transaction.updated_at <= cutoff,
            )
        ).all()

        if not txns:
            return 0

        for txn in txns:
            txn.auto_provider = RETRY_QUEUE_PROVIDER
            txn.needs_review = False
            txn.api_retry_count = 0
            txn.api_retry_provider = txn.api_retry_provider or DEFAULT_EXTERNAL_PROVIDER
            txn.api_retry_last_error = None

        db.commit()
        logger.info("Auto-requeued %d retry_failed transactions", len(txns))
        return len(txns)
    finally:
        db.close()
