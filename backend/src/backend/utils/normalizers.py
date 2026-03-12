from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from decimal import Decimal

import pandas as pd


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00A0", " ").replace("\u200B", "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def clean_amount(value: object) -> Decimal | None:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[^0-9.()-]", "", text)
    text = text.replace("(", "-").replace(")", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def parse_datetime(value: object) -> datetime | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def sha256_of(parts: list[str]) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_dedupe_hash(platform: str, occurred_at: datetime, amount: Decimal, merchant: str | None, item: str | None) -> str:
    return sha256_of(
        [
            normalize_text(platform),
            occurred_at.isoformat(),
            str(amount),
            normalize_text(merchant),
            normalize_text(item),
        ]
    )


def build_classification_hash(merchant: str | None, item: str | None, note: str | None, direction: str) -> str:
    return sha256_of([normalize_text(merchant), normalize_text(item), normalize_text(note), normalize_text(direction)])
