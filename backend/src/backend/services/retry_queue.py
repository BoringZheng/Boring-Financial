from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import select

from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.models import Transaction
from backend.services.classifiers import classify_transaction

logger = logging.getLogger(__name__)


def _retry_one(db, txn: Transaction) -> None:
    """Classify a single transaction. Errors and requeueing are handled
    inside classify_transaction -> CompositeClassifier.classify."""
    classify_transaction(
        db, txn, txn.user_id,
        provider_override=None,
        auto_commit=True,
        force_refresh=True,
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
                .where(Transaction.auto_provider == "retry_queue")
                .order_by(Transaction.api_retry_count.asc())
                .limit(1)
            ).first()

            if txn is None:
                # Queue is empty — wait before polling again
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

    Finds every transaction where ``needs_review`` is True **and**
    ``auto_reason`` contains ``"external api"`` (which covers both
    *"external api failed"* and *"external api timeout"* patterns).
    Sets ``auto_provider = "retry_queue"``, ``needs_review = False``,
    and ``api_retry_count = 0`` so the background worker picks them up.
    """
    db = SessionLocal()
    try:
        txns = db.scalars(
            select(Transaction).where(
                Transaction.needs_review == True,
                Transaction.auto_reason.contains("external api"),
            )
        ).all()

        if not txns:
            return 0

        for txn in txns:
            txn.auto_provider = "retry_queue"
            txn.needs_review = False
            txn.api_retry_count = 0

        db.commit()
        logger.info("Migrated %d existing timeout transactions to retry queue", len(txns))
        return len(txns)
    finally:
        db.close()


def requeue_all_external_api_failures() -> int:
    """Admin action: push ALL transactions with external-api issues back into
    the retry queue, regardless of their current status.

    This covers:
    - transactions already in ``retry_queue`` (reset retry count)
    - transactions that fell back to rules after exhausting retries
    - transactions manually reviewed but originally from API failures
    - any transaction whose ``auto_reason`` mentions "external api"

    Returns the number of transactions queued.
    """
    db = SessionLocal()
    try:
        txns = db.scalars(
            select(Transaction).where(
                Transaction.auto_reason.contains("external api"),
            )
        ).all()

        if not txns:
            logger.info("No transactions with external API issues found")
            return 0

        for txn in txns:
            txn.auto_provider = "retry_queue"
            txn.needs_review = False
            txn.api_retry_count = 0

        db.commit()
        logger.info("Requeued %d transactions into retry queue", len(txns))
        return len(txns)
    finally:
        db.close()
