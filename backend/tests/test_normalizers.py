from datetime import datetime
from decimal import Decimal

from backend.utils.normalizers import build_classification_hash, build_dedupe_hash, normalize_text


def test_normalize_text_handles_spacing_and_case():
    assert normalize_text("  HeLLo　World  ") == "hello world"


def test_hash_builders_are_stable():
    dedupe = build_dedupe_hash("WeChat", datetime(2025, 1, 1, 12, 0, 0), Decimal("12.50"), "KFC", "午餐")
    classification = build_classification_hash("KFC", "午餐", "无", "支出")
    assert len(dedupe) == 64
    assert len(classification) == 64
