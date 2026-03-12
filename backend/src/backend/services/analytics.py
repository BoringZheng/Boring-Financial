from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Category, ImportBatch, Transaction


def dashboard_summary(
    db: Session,
    user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: int | None = None,
    uploaded_file_ids: list[int] | None = None,
) -> dict:
    query = select(Transaction).where(Transaction.user_id == user_id)
    if date_from is not None:
        query = query.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_at <= date_to)
    if category_id is not None:
        query = query.where((Transaction.final_category_id == category_id) | (Transaction.auto_category_id == category_id))
    if uploaded_file_ids:
        query = query.where(Transaction.uploaded_file_id.in_(uploaded_file_ids))

    transactions = db.scalars(query.order_by(Transaction.occurred_at.asc())).all()
    category_ids = {
        resolved_category_id
        for transaction in transactions
        for resolved_category_id in [transaction.final_category_id or transaction.auto_category_id]
        if resolved_category_id is not None
    }
    category_lookup = (
        {
            category.id: category.name
            for category in db.scalars(select(Category).where(Category.id.in_(category_ids))).all()
        }
        if category_ids
        else {}
    )

    expense_total = sum((transaction.amount for transaction in transactions if transaction.type == "支出"), Decimal("0"))
    income_total = sum((transaction.amount for transaction in transactions if transaction.type == "收入"), Decimal("0"))
    pending_review_count = sum(1 for transaction in transactions if transaction.needs_review)
    transaction_count = len(transactions)

    merchant_map: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"amount": Decimal("0"), "transaction_count": 0}
    )
    category_map: dict[str, dict[str, Decimal | int | None]] = defaultdict(
        lambda: {"amount": Decimal("0"), "transaction_count": 0, "category_id": None}
    )
    trend_map: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"expense": Decimal("0"), "income": Decimal("0")})

    for transaction in transactions:
        trend_key = transaction.occurred_at.strftime("%Y-%m-%d")
        if transaction.type == "支出":
            trend_map[trend_key]["expense"] += transaction.amount
        else:
            trend_map[trend_key]["income"] += transaction.amount

        if transaction.type != "支出":
            continue

        merchant_name = transaction.merchant or "未知商户"
        merchant_map[merchant_name]["amount"] += transaction.amount
        merchant_map[merchant_name]["transaction_count"] += 1

        resolved_category_id = transaction.final_category_id or transaction.auto_category_id
        category_name = category_lookup.get(resolved_category_id, "未分类")
        category_map[category_name]["amount"] += transaction.amount
        category_map[category_name]["transaction_count"] += 1
        category_map[category_name]["category_id"] = resolved_category_id

    jobs = db.scalars(
        select(ImportBatch).where(ImportBatch.user_id == user_id).order_by(ImportBatch.created_at.desc()).limit(5)
    ).all()

    return {
        "expense_total": expense_total,
        "income_total": income_total,
        "net_total": income_total - expense_total,
        "transaction_count": transaction_count,
        "pending_review_count": pending_review_count,
        "top_merchants": [
            {
                "merchant": merchant,
                "amount": payload["amount"],
                "transaction_count": payload["transaction_count"],
            }
            for merchant, payload in sorted(
                merchant_map.items(), key=lambda item: item[1]["amount"], reverse=True
            )[:10]
        ],
        "category_breakdown": [
            {
                "category_id": payload["category_id"],
                "category_name": category_name,
                "amount": payload["amount"],
                "transaction_count": payload["transaction_count"],
            }
            for category_name, payload in sorted(
                category_map.items(), key=lambda item: item[1]["amount"], reverse=True
            )
        ],
        "expense_trend": [
            {
                "date": trend_date,
                "expense": payload["expense"],
                "income": payload["income"],
            }
            for trend_date, payload in sorted(trend_map.items(), key=lambda item: item[0])
        ],
        "recent_jobs": [
            {
                "id": job.id,
                "status": job.status,
                "processed_count": job.processed_count,
                "total_count": job.total_count,
                "source_count": job.source_count,
                "progress_percent": job.progress_percent,
            }
            for job in jobs
        ],
    }
