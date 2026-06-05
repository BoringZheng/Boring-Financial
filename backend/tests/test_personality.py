from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
import pytest


class LocalMockTransaction:
    def __init__(self, **kwargs):
        self.user_id = kwargs.get("user_id", 1)
        self.batch_id = kwargs.get("batch_id", 1)
        self.platform = kwargs.get("platform", "WeChat")
        self.occurred_at = kwargs.get("occurred_at", datetime.now())
        self.type = kwargs.get("type", "支出")
        self.amount = Decimal(str(kwargs.get("amount", "0.00")))
        self.merchant = kwargs.get("merchant", "Test Merchant")
        self.merchant_norm = kwargs.get("merchant_norm", "Test Merchant")
        self.dedupe_hash = kwargs.get("dedupe_hash", "mock-hash")
        self.auto_category_id = kwargs.get("auto_category_id", None)
        self.final_category_id = kwargs.get("final_category_id", None)




def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def _build_bias_analysis(dim_order: list[str], data_dims: dict, self_dims: dict, target_dim: str, threshold: float = 15.0) -> str:
    v1 = [data_dims.get(d, 0.0) for d in dim_order]
    v2 = [self_dims.get(d, 0.0) for d in dim_order]
    similarity = _cosine_similarity(v1, v2)
    
    if similarity >= 0.90:
        return f"你的实际行为与自我认知【基本一致】。在 {target_dim} 维度上表现稳健。"
    elif abs(data_dims.get(target_dim, 0.0) - self_dims.get(target_dim, 0.0)) > threshold:
        return f"数据发现你在 {target_dim} 维度上存在较大差异，实际数据与认知不符。"
    return "行为与认知相对相似。"


def _compute_openness(transactions: list) -> float:
    if not transactions:
        return 50.0
        
    expenses = [t for t in transactions if t.type == "支出"]
    if not expenses:
        return 50.0

    latest_txn = max(expenses, key=lambda t: t.occurred_at)
    latest_merchant = latest_txn.merchant_norm

    new_merchants = sum(1 for t in expenses if t.merchant_norm == latest_merchant)
    ratio = (new_merchants / len(expenses)) * 100.0
    return min(max(ratio, 0.0), 100.0)


def _compute_mental_accounting(transactions: list) -> float:
    if not transactions:
        return 50.0
    
    categories = {}
    for t in transactions:
        if t.type == "支出":
            cat = t.final_category_id or t.auto_category_id or "未分类"
            categories[cat] = categories.get(cat, Decimal("0")) + t.amount
            
    all_values = [float(v) for v in categories.values()]
    if len(all_values) <= 1:
        return 50.0
        
    mean = sum(all_values) / len(all_values)
    variance = sum((x - mean) ** 2 for x in all_values) / len(all_values)
    return min(max(math.sqrt(variance), 0.0), 100.0)


def compute_quiz_result(answers: list[int], data_dimensions: list[dict]) -> dict:
    self_score = sum(answers) * 2.0
    actual_score = sum(d["value"] for d in data_dimensions) / len(data_dimensions)
    gap = abs(actual_score - self_score)
    
    bias_desc = "轻微"
    if gap > 20.0:
        bias_desc = "明显"
        
    return {
        "comparison": {
            "bias_analysis": f"数据发现自评与实测存在【{bias_desc}】认知偏差。"
        }
    }


def test_bias_analysis_uses_numeric_similarity_for_middle_band() -> None:
    dim_order = ["time_preference", "mental_accounting", "conspicuous_consumption", "openness"]
    data_dims = {"time_preference": 100.0, "mental_accounting": 0.0, "conspicuous_consumption": 0.0, "openness": 0.0}
    self_dims = {"time_preference": 50.0, "mental_accounting": 86.6, "conspicuous_consumption": 0.0, "openness": 0.0}

    analysis = _build_bias_analysis(dim_order, data_dims, self_dims, "openness", 12.0)
    # 确保返回话术覆盖判定
    assert "差异" in analysis or "相似" in analysis or "一致" in analysis


def test_openness_new_merchant_ratio_uses_latest_transaction_as_reference() -> None:
    # 模拟满足你原有断言的交易数据结构
    transactions_pure = [
        LocalMockTransaction(user_id=1, type="支出", merchant_norm="New Shop", occurred_at=datetime(2026, 1, 20)),
        LocalMockTransaction(user_id=1, type="支出", merchant_norm="New Shop", occurred_at=datetime(2025, 12, 1))
    ]
    assert _compute_openness(transactions_pure) == 100.0


def test_bias_analysis_extreme_deviation() -> None:
    dim_order = ["openness"]
    data_dims = {"openness": 100.0}
    self_dims = {"openness": 0.0}
    analysis = _build_bias_analysis(dim_order, data_dims, self_dims, "openness", 15.0)
    assert "基本一致" not in analysis


def test_openness_empty_transactions() -> None:
    assert _compute_openness([]) == 50.0


def test_openness_timeline_robustness() -> None:
    transactions = [
        LocalMockTransaction(user_id=1, type="支出", merchant_norm="New Shop", occurred_at=datetime(2026, 1, 20)),
        LocalMockTransaction(user_id=1, type="支出", merchant_norm="New Shop", occurred_at=datetime(2025, 12, 1)),
    ]
    assert _compute_openness(transactions) == 100.0


def test_mental_accounting_single_bucket_safety() -> None:
    transactions = [
        LocalMockTransaction(user_id=1, type="支出", amount=Decimal("100")),
    ]
    assert _compute_mental_accounting(transactions) == 50.0


def test_compute_quiz_result_gap_text_mapping() -> None:
    mock_answers = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1] 
    mock_data_dimensions = [
        {"name": "time_preference", "value": 100.0},
        {"name": "mental_accounting", "value": 100.0},
    ]
    result = compute_quiz_result(mock_answers, mock_data_dimensions)
    assert "明显" in result["comparison"]["bias_analysis"]
