from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models import Category, CategoryRule

DEFAULT_CATEGORIES = [
    "未分类",
    "餐饮",
    "交通",
    "购物",
    "生活缴费",
    "住房",
    "医疗",
    "娱乐",
    "学习",
    "收入",
    "转账",
]


def _read_category_map(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    last_error = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030", "cp936", "latin1"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception as exc:
            last_error = exc
    if last_error:
        print(f"Failed to load category map: {last_error}")
    return None


def seed_defaults(db: Session) -> None:
    existing = db.scalar(select(Category.id).limit(1))
    if existing:
        return

    categories: dict[str, Category] = {}
    for name in DEFAULT_CATEGORIES:
        category = Category(name=name, is_system=True, is_active=True)
        db.add(category)
        db.flush()
        categories[name] = category

    df = _read_category_map(settings.category_map_path)
    if df is not None:
        df.columns = [str(column).replace("\ufeff", "").strip().lower() for column in df.columns]
        for _, row in df.iterrows():
            category_name = str(row.get("category", "")).strip()
            if not category_name:
                continue
            category = categories.get(category_name)
            if category is None:
                category = Category(name=category_name, is_system=True, is_active=True)
                db.add(category)
                db.flush()
                categories[category_name] = category
            rule = CategoryRule(
                category_id=category.id,
                subcategory_name=str(row.get("subcategory", "")).strip() or None,
                priority=int(float(row.get("priority", 0) or 0)),
                merchant_pattern=str(row.get("merchant", "")).strip() or None,
                keyword_pattern=str(row.get("keyword", "")).strip() or None,
                is_regex=str(row.get("regex", "0")).strip().lower() in {"1", "true"},
            )
            db.add(rule)

    db.commit()
