from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from backend.models import Transaction
from backend.services.personality import _build_bias_analysis, _compute_openness


def test_bias_analysis_uses_numeric_similarity_for_middle_band() -> None:
    dim_order = ["time_preference", "mental_accounting", "conspicuous_consumption", "openness"]
    data_dims = {
        "time_preference": 100.0,
        "mental_accounting": 0.0,
        "conspicuous_consumption": 0.0,
        "openness": 0.0,
    }
    self_dims = {
        "time_preference": 50.0,
        "mental_accounting": 86.6,
        "conspicuous_consumption": 0.0,
        "openness": 0.0,
    }

    analysis = _build_bias_analysis(dim_order, data_dims, self_dims, "openness", 12.0)

    assert "基本一致" in analysis


def test_openness_new_merchant_ratio_uses_latest_transaction_as_reference() -> None:
    transactions = [
        Transaction(
            user_id=1,
            batch_id=1,
            platform="WeChat",
            occurred_at=datetime(2025, 12, 1, 12, 0, 0),
            type="支出",
            amount=Decimal("20.00"),
            merchant="Old Shop",
            merchant_norm="Old Shop",
            dedupe_hash="old-shop",
        ),
        Transaction(
            user_id=1,
            batch_id=1,
            platform="WeChat",
            occurred_at=datetime(2026, 1, 20, 12, 0, 0),
            type="支出",
            amount=Decimal("30.00"),
            merchant="New Shop",
            merchant_norm="New Shop",
            dedupe_hash="new-shop",
        ),
    ]

    assert _compute_openness(transactions) == 100.0
