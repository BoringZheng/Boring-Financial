"""Reliability metrics for import batches, reports, and classification coverage."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import ImportBatch, ReportJob, Transaction


def reliability_metrics(db: Session, user_id: int | None = None) -> dict:
    """Return reliability metrics optionally scoped to a single user."""

    # --- Import batches ---
    batch_query = select(ImportBatch)
    if user_id is not None:
        batch_query = batch_query.where(ImportBatch.user_id == user_id)
    batches = db.scalars(batch_query).all()

    total_import_batches = len(batches)
    import_success_count = sum(1 for b in batches if b.status == "done")
    import_partial_failed_count = sum(1 for b in batches if b.status == "partial_failed")
    import_failed_count = sum(1 for b in batches if b.status == "failed")

    import_success_rate = _rate(import_success_count, total_import_batches)
    import_partial_failure_rate = _rate(import_partial_failed_count, total_import_batches)
    import_failure_rate = _rate(import_failed_count, total_import_batches)

    # --- Report jobs ---
    report_query = select(ReportJob)
    if user_id is not None:
        report_query = report_query.where(ReportJob.user_id == user_id)
    reports = db.scalars(report_query).all()

    total_report_jobs = len(reports)
    report_done_count = sum(1 for r in reports if r.status == "done")
    report_success_rate = _rate(report_done_count, total_report_jobs)

    # --- Transactions ---
    tx_query = select(Transaction)
    if user_id is not None:
        tx_query = tx_query.where(Transaction.user_id == user_id)
    transactions = db.scalars(tx_query).all()

    total_transactions = len(transactions)
    pending_review_count = sum(1 for t in transactions if t.needs_review)
    classified_transaction_count = sum(1 for t in transactions if t.auto_category_id is not None or t.final_category_id is not None)

    pending_review_rate = _rate(pending_review_count, total_transactions)
    classification_coverage_rate = _rate(classified_transaction_count, total_transactions)

    return {
        "total_import_batches": total_import_batches,
        "import_success_count": import_success_count,
        "import_partial_failed_count": import_partial_failed_count,
        "import_failed_count": import_failed_count,
        "import_success_rate": import_success_rate,
        "import_partial_failure_rate": import_partial_failure_rate,
        "import_failure_rate": import_failure_rate,
        "total_report_jobs": total_report_jobs,
        "report_done_count": report_done_count,
        "report_success_rate": report_success_rate,
        "total_transactions": total_transactions,
        "pending_review_count": pending_review_count,
        "pending_review_rate": pending_review_rate,
        "classified_transaction_count": classified_transaction_count,
        "classification_coverage_rate": classification_coverage_rate,
    }


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((count / total) * 100, 2)
