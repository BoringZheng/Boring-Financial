from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.base_class import Base
from backend.models import Category, ClassificationCache, Transaction, User
from backend.models import Transaction
from backend.services import classifiers as classifiers_module
from backend.services.classifiers import (
    RETRY_FAILED_PROVIDER,
    RETRY_QUEUE_PROVIDER,
    ClassificationOutput,
    CompositeClassifier,
    OpenAICompatibleClassifier,
    classify_transaction,
)


def test_model_prompt_prioritizes_merchant_and_summary() -> None:
    classifier = OpenAICompatibleClassifier(
        api_base="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )
    transaction = Transaction(
        user_id=1,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("25.50"),
        merchant="瑞幸咖啡",
        item="生椰拿铁",
        method="零钱",
        status="支付成功",
        note="上午加班提神",
        merchant_norm="瑞幸咖啡",
        item_norm="生椰拿铁",
        note_norm="上午加班提神",
        dedupe_hash="hash-prompt",
    )

    prompt = classifier._build_prompt(transaction, ["餐饮", "交通"])

    assert "merchant_text" in prompt[0]["content"]
    assert "summary_text" in prompt[0]["content"]
    assert "优先依据商户和摘要判断，直接给结论" in prompt[1]["content"]
    assert "瑞幸咖啡" in prompt[1]["content"]
    assert "生椰拿铁 | 上午加班提神" in prompt[1]["content"]
    assert "reason 必须非常短" in prompt[0]["content"]


def test_call_model_retries_after_timeout(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"category":"餐饮","confidence":0.9,"reason":"ok"}'}}]}

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def post(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ReadTimeout("timed out")
            return FakeResponse()

    fake_client = FakeClient()
    monkeypatch.setattr(classifiers_module, "get_http_client", lambda *args, **kwargs: fake_client)
    monkeypatch.setattr(classifiers_module, "sleep", lambda *_args, **_kwargs: None)

    classifier = OpenAICompatibleClassifier(
        api_base="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )

    response_text = classifier._call_model([{"role": "user", "content": "test"}])

    assert '"category":"餐饮"' in response_text
    assert fake_client.calls == 2


def test_call_model_limits_output_tokens(monkeypatch) -> None:
    captured_payload: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"category":"餐饮","confidence":0.9,"reason":"咖啡"}'}}]}

    class FakeClient:
        def post(self, _path: str, json: dict):
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr(classifiers_module, "get_http_client", lambda *args, **kwargs: FakeClient())

    classifier = OpenAICompatibleClassifier(
        api_base="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )

    classifier._call_model([{"role": "user", "content": "test"}])

    assert captured_payload["max_tokens"] == 80
    assert captured_payload["top_p"] == 0.1


def test_duplicate_cache_insert_does_not_poison_session() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    user = User(username="cache-user", email="cache@example.com", hashed_password="hashed")
    category = Category(name="餐饮", is_system=True, is_active=True)
    transaction = Transaction(
        user_id=1,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("18.00"),
        merchant="瑞幸咖啡",
        item="拿铁",
        method="零钱",
        status="支付成功",
        note="",
        merchant_norm="瑞幸咖啡",
        item_norm="拿铁",
        note_norm="",
        dedupe_hash="cache-hash",
    )
    db.add_all([user, category])
    db.commit()
    db.refresh(user)
    db.refresh(category)
    transaction.user_id = user.id
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    output = ClassificationOutput(
        category_id=category.id,
        subcategory_name="咖啡",
        confidence=0.9,
        reason="咖啡消费",
        provider="openai_compatible_api",
        raw_response='{"category":"餐饮"}',
    )
    classifier = CompositeClassifier()

    classifier._save_cache(db, user.id, transaction, output, auto_commit=False)
    classifier._save_cache(db, user.id, transaction, output, auto_commit=False)
    classifier._store_result(db, transaction, output, auto_commit=True)

    caches = db.scalars(select(ClassificationCache)).all()
    assert len(caches) == 1
    assert transaction.auto_provider == "openai_compatible_api"


def test_external_classification_is_queued_without_calling_model(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    user = User(username="queue-user", email="queue@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    transaction = Transaction(
        user_id=user.id,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("18.00"),
        merchant="测试商户",
        item="午餐",
        method="零钱",
        status="支付成功",
        note="",
        merchant_norm="测试商户",
        item_norm="午餐",
        note_norm="",
        dedupe_hash="queue-hash",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("external model should not be called inline")

    monkeypatch.setattr(OpenAICompatibleClassifier, "classify", fail_if_called)

    output = classify_transaction(db, transaction, user.id)

    assert output.provider == RETRY_QUEUE_PROVIDER
    assert transaction.auto_provider == RETRY_QUEUE_PROVIDER
    assert transaction.api_retry_provider == "openai_compatible_api"
    assert transaction.needs_review is False


def test_non_timeout_external_error_falls_back_without_requeue(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    user = User(username="fallback-user", email="fallback@example.com", hashed_password="hashed")
    transaction = Transaction(
        user_id=1,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("18.00"),
        merchant="测试商户",
        item="午餐",
        method="零钱",
        status="支付成功",
        note="",
        merchant_norm="测试商户",
        item_norm="午餐",
        note_norm="",
        dedupe_hash="fallback-hash",
    )
    db.add_all([user, transaction])
    db.commit()
    db.refresh(user)
    transaction.user_id = user.id
    db.commit()
    db.refresh(transaction)

    def raise_non_timeout(*_args, **_kwargs):
        raise ValueError("bad api key")

    monkeypatch.setattr(CompositeClassifier, "_classify_with_provider", raise_non_timeout)

    output = CompositeClassifier().classify(
        db,
        transaction,
        user.id,
        provider_override="openai_compatible_api",
        enqueue_external=False,
    )

    assert output.provider == "rule"
    assert transaction.auto_provider == "rule"
    assert transaction.api_retry_count == 0
    assert transaction.needs_review is True


def test_exhausted_timeout_is_not_sent_to_manual_review(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    user = User(username="timeout-user", email="timeout@example.com", hashed_password="hashed")
    transaction = Transaction(
        user_id=1,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("18.00"),
        merchant="测试商户",
        item="午餐",
        method="零钱",
        status="支付成功",
        note="",
        merchant_norm="测试商户",
        item_norm="午餐",
        note_norm="",
        dedupe_hash="timeout-hash",
        api_retry_count=4,
        api_retry_provider="openai_compatible_api",
    )
    db.add_all([user, transaction])
    db.commit()
    db.refresh(user)
    transaction.user_id = user.id
    db.commit()
    db.refresh(transaction)

    def raise_timeout(*_args, **_kwargs):
        raise RuntimeError("external api timeout") from httpx.ReadTimeout("timed out")

    monkeypatch.setattr(classifiers_module.settings, "retry_queue_max_retries", 5)
    monkeypatch.setattr(CompositeClassifier, "_classify_with_provider", raise_timeout)

    output = CompositeClassifier().classify(
        db,
        transaction,
        user.id,
        provider_override="openai_compatible_api",
        enqueue_external=False,
    )

    assert output.provider == RETRY_FAILED_PROVIDER
    assert transaction.auto_provider == RETRY_FAILED_PROVIDER
    assert transaction.api_retry_count == 5
    assert transaction.needs_review is False
