from __future__ import annotations

import json
import importlib.util
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from time import sleep

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings
from backend.models import Category, CategoryRule, ClassificationCache, ClassificationResult, Transaction
from backend.utils.normalizers import build_classification_hash, normalize_text

PROMPT_VERSION = "v2"
EXTERNAL_MODEL_PROVIDERS = {"openai_compatible_api", "local_model"}
RETRY_QUEUE_PROVIDER = "retry_queue"
RETRY_FAILED_PROVIDER = "retry_failed"
DEFAULT_EXTERNAL_PROVIDER = "openai_compatible_api"


@dataclass
class ClassificationOutput:
    category_id: int | None
    subcategory_name: str | None
    confidence: float
    reason: str
    provider: str
    raw_response: str | None = None


@lru_cache(maxsize=8)
def get_http_client(api_base: str, api_key: str, timeout: float) -> httpx.Client:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    http2_enabled = importlib.util.find_spec("h2") is not None
    request_timeout = httpx.Timeout(
        connect=settings.model_connect_timeout_seconds,
        read=timeout,
        write=10.0,
        pool=5.0,
    )
    return httpx.Client(
        base_url=api_base.rstrip("/"),
        timeout=request_timeout,
        headers=headers,
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        http2=http2_enabled,
    )


class RuleBasedClassifier:
    provider_name = "rule"

    def classify(self, db: Session, transaction: Transaction, user_id: int) -> ClassificationOutput | None:
        rules = db.scalars(
            select(CategoryRule)
            .where((CategoryRule.user_id == None) | (CategoryRule.user_id == user_id))
            .order_by(CategoryRule.priority.desc(), CategoryRule.id.asc())
        ).all()
        merchant = normalize_text(transaction.merchant)
        item = normalize_text(transaction.item)
        note = normalize_text(transaction.note)
        item_note = f"{item} {note}".strip()
        full_text = f"{merchant} {item} {note}".strip()

        for rule in rules:
            if not self._matches(rule, merchant, item_note, full_text):
                continue
            return ClassificationOutput(
                category_id=rule.category_id,
                subcategory_name=rule.subcategory_name,
                confidence=0.99,
                reason="matched category rule",
                provider=self.provider_name,
            )
        return None

    def _matches(self, rule: CategoryRule, merchant: str, item_note: str, full_text: str) -> bool:
        target = full_text if not rule.keyword_pattern else merchant
        if rule.merchant_pattern and not self._match_text(rule.merchant_pattern, target, rule.is_regex):
            return False
        if rule.keyword_pattern and not self._match_text(rule.keyword_pattern, item_note, rule.is_regex):
            return False
        return True

    @staticmethod
    def _match_text(pattern: str, text: str, is_regex: bool) -> bool:
        normalized = normalize_text(pattern)
        if is_regex:
            try:
                return re.search(normalized, text, re.IGNORECASE) is not None
            except re.error:
                return False
        return any(token in text for token in normalized.split("|") if token)


class OpenAICompatibleClassifier:
    provider_name = "openai_compatible_api"

    def __init__(self, api_base: str, api_key: str, model: str, provider_name: str | None = None) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = settings.model_timeout_seconds
        if provider_name:
            self.provider_name = provider_name

    def classify(self, db: Session, transaction: Transaction, user_id: int) -> ClassificationOutput:
        categories = db.scalars(
            select(Category).where(((Category.user_id == None) | (Category.user_id == user_id)) & (Category.is_active == True))
        ).all()
        category_names = [category.name for category in categories]
        prompt = self._build_prompt(transaction, category_names)
        response_text = self._call_model(prompt)
        payload = self._parse_response(response_text)
        category = next((item for item in categories if item.name == payload.get("category")), None)
        return ClassificationOutput(
            category_id=category.id if category else None,
            subcategory_name=payload.get("subcategory"),
            confidence=self._coerce_confidence(payload.get("confidence", 0.5)),
            reason=str(payload.get("reason", "model classification")),
            provider=self.provider_name,
            raw_response=response_text,
        )

    def _build_prompt(self, transaction: Transaction, category_names: list[str]) -> list[dict]:
        merchant_text = str(transaction.merchant or "").strip()
        summary_text = self._build_summary_text(transaction)
        return [
            {
                "role": "system",
                "content": (
                    "你是账单分类助手。根据 merchant_text 和 summary_text 快速判断消费场景。"
                    "优先看商户和摘要，不输出思考过程，不解释废话。"
                    "如果 merchant_text 与 summary_text 冲突，采用更具体的一方。"
                    "只输出严格 JSON 对象，不要包含在代码块中，不要添加任何其他文本。"
                    '样例输出：{"category": "餐饮", "subcategory": "快餐", "confidence": 0.95, "reason": "肯德基商户"}'
                    "reason 必须非常短，控制在 12 个汉字以内。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "allowed_categories": category_names,
                        "classification_focus": {
                            "primary_fields": ["merchant_text", "summary_text"],
                            "instruction": "优先依据商户和摘要判断，直接给结论，reason 尽量短。",
                        },
                        "transaction": {
                            "platform": transaction.platform,
                            "type": transaction.type,
                            "amount": str(transaction.amount),
                            "merchant_text": merchant_text,
                            "summary_text": summary_text,
                            "raw_item": transaction.item,
                            "raw_note": transaction.note,
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    @staticmethod
    def _build_summary_text(transaction: Transaction) -> str:
        parts = [str(transaction.item or "").strip(), str(transaction.note or "").strip()]
        return " | ".join(part for part in parts if part) or "无摘要"

    def _call_model(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "top_p": 0.1,
            "max_tokens": min(settings.model_max_output_tokens, 80),
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        client = get_http_client(self.api_base, self.api_key, self.timeout)
        last_error: Exception | None = None
        for attempt in range(settings.model_max_retries + 1):
            try:
                response = client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                finish = choice.get("finish_reason", "")

                # DeepSeek json_object known issue: occasionally returns empty content
                if not content.strip():
                    if "response_format" in payload:
                        payload.pop("response_format")
                        continue
                    break

                # Output was truncated — double max_tokens and retry
                if finish == "length":
                    payload["max_tokens"] = payload["max_tokens"] * 2
                    continue

                return content
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                last_error = exc
                if attempt >= settings.model_max_retries:
                    break
                sleep(min(0.5 * (attempt + 1), 1.5))
        raise RuntimeError(
            f"external api timeout after {settings.model_max_retries + 1} attempts"
        ) from last_error

    def _parse_response(self, response_text: str) -> dict:
        stripped = response_text.strip()

        # 1. Try extracting JSON from markdown code fence (```json / ```)
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Try finding a JSON object in the text (model may have added surrounding text)
        brace_match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 3. Direct parse
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        return {"category": "未分类", "subcategory": None, "confidence": 0.3, "reason": response_text}

    @staticmethod
    def _coerce_confidence(value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(confidence, 1.0))


class LocalModelClassifier(OpenAICompatibleClassifier):
    def __init__(self) -> None:
        super().__init__(
            api_base=settings.local_model_api_base,
            api_key=settings.local_model_api_key,
            model=settings.local_model_name,
            provider_name="local_model",
        )


class CompositeClassifier:
    provider_name = "composite"

    def __init__(self) -> None:
        self.rule_classifier = RuleBasedClassifier()
        self.api_classifier = OpenAICompatibleClassifier(
            api_base=settings.openai_api_base,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        self.local_classifier = LocalModelClassifier()

    def _cached_output(
        self, db: Session, user_id: int, transaction: Transaction, provider_name: str
    ) -> ClassificationOutput | None:
        cached = self._lookup_cache(db, user_id, transaction, provider_name)
        if cached is None:
            return None
        return ClassificationOutput(
            category_id=cached.category_id,
            subcategory_name=cached.subcategory_name,
            confidence=float(cached.confidence or 0),
            reason=cached.reason or "cache hit",
            provider=cached.provider,
            raw_response=cached.raw_response,
        )

    def _classify_with_provider(
        self, db: Session, transaction: Transaction, user_id: int, provider_name: str, auto_commit: bool = True, *, force_refresh: bool = False
    ) -> ClassificationOutput:
        if not force_refresh:
            cached_output = self._cached_output(db, user_id, transaction, provider_name)
            if cached_output is not None:
                self._store_result(db, transaction, cached_output, auto_commit=auto_commit)
                return cached_output

        if provider_name == "local_model":
            model_output = self.local_classifier.classify(db, transaction, user_id)
        else:
            model_output = self.api_classifier.classify(db, transaction, user_id)

        self._save_cache(db, user_id, transaction, model_output, auto_commit=False)
        self._store_result(db, transaction, model_output, auto_commit=auto_commit)
        return model_output

    def _enqueue_external_classification(
        self,
        db: Session,
        transaction: Transaction,
        provider_name: str,
        auto_commit: bool,
        *,
        reset_retry_count: bool = True,
    ) -> ClassificationOutput:
        if reset_retry_count:
            transaction.api_retry_count = 0
        transaction.api_retry_provider = provider_name
        transaction.api_retry_last_error = None
        transaction.auto_category_id = None
        transaction.auto_subcategory_name = None
        transaction.auto_confidence = Decimal("0.0")
        transaction.auto_provider = RETRY_QUEUE_PROVIDER
        transaction.auto_reason = f"queued for external model classification: {provider_name}"
        transaction.needs_review = False
        if auto_commit:
            db.commit()
        return ClassificationOutput(
            category_id=None,
            subcategory_name=None,
            confidence=0.0,
            reason=transaction.auto_reason,
            provider=RETRY_QUEUE_PROVIDER,
            raw_response=None,
        )

    @staticmethod
    def _is_retryable_external_error(exc: Exception) -> bool:
        current: BaseException | None = exc
        while current is not None:
            if isinstance(current, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout)):
                return True
            current = current.__cause__
        return False

    def _queue_for_retry(
        self, db: Session, transaction: Transaction, provider_name: str, exc: Exception, auto_commit: bool
    ) -> ClassificationOutput | None:
        """Queue tx for background retry if under limit. Returns None if limit reached."""
        if not self._is_retryable_external_error(exc):
            return None
        transaction.api_retry_count += 1
        transaction.api_retry_last_error = str(exc)
        transaction.api_retry_provider = provider_name
        if transaction.api_retry_count >= settings.retry_queue_max_retries:
            return None
        transaction.auto_provider = RETRY_QUEUE_PROVIDER
        transaction.auto_reason = (
            f"external api timeout, retry {transaction.api_retry_count}"
            f"/{settings.retry_queue_max_retries}: {exc}"
        )
        transaction.auto_confidence = Decimal("0.0")
        transaction.needs_review = False
        if auto_commit:
            db.commit()
        return ClassificationOutput(
            category_id=None,
            subcategory_name=None,
            confidence=0.0,
            reason=f"queued for retry ({transaction.api_retry_count}/{settings.retry_queue_max_retries})",
            provider=RETRY_QUEUE_PROVIDER,
            raw_response=None,
        )

    def _mark_retry_failed(
        self, db: Session, transaction: Transaction, provider_name: str, exc: Exception, auto_commit: bool
    ) -> ClassificationOutput:
        reason = f"external api retry exhausted after {transaction.api_retry_count} attempts: {exc}"
        transaction.auto_category_id = None
        transaction.auto_subcategory_name = None
        transaction.auto_confidence = Decimal("0.0")
        transaction.auto_provider = RETRY_FAILED_PROVIDER
        transaction.auto_reason = reason
        transaction.api_retry_provider = provider_name
        transaction.api_retry_last_error = str(exc)
        transaction.needs_review = False
        db.add(
            ClassificationResult(
                transaction_id=transaction.id,
                category_id=None,
                subcategory_name=None,
                confidence=Decimal("0.0"),
                reason=reason,
                provider=RETRY_FAILED_PROVIDER,
                prompt_version=PROMPT_VERSION,
                raw_response=None,
            )
        )
        if auto_commit:
            db.commit()
        return ClassificationOutput(None, None, 0.0, reason, RETRY_FAILED_PROVIDER)

    def _rule_fallback(
        self, db: Session, transaction: Transaction, user_id: int, fallback_reason: str, auto_commit: bool = True
    ) -> ClassificationOutput:
        rule_result = self.rule_classifier.classify(db, transaction, user_id)
        if rule_result:
            rule_result.reason = f"{rule_result.reason}; {fallback_reason}"
            self._store_result(db, transaction, rule_result, auto_commit=auto_commit)
            return rule_result

        fallback_output = ClassificationOutput(
            category_id=None,
            subcategory_name=None,
            confidence=0.0,
            reason=fallback_reason,
            provider="rule",
            raw_response=None,
        )
        self._store_result(db, transaction, fallback_output, auto_commit=auto_commit)
        return fallback_output

    def classify(
        self,
        db: Session,
        transaction: Transaction,
        user_id: int,
        provider_override: str | None = None,
        auto_commit: bool = True,
        *,
        force_refresh: bool = False,
        enqueue_external: bool = True,
    ) -> ClassificationOutput:
        if provider_override in EXTERNAL_MODEL_PROVIDERS:
            if enqueue_external:
                if not force_refresh:
                    cached_output = self._cached_output(db, user_id, transaction, provider_override)
                    if cached_output is not None:
                        self._store_result(db, transaction, cached_output, auto_commit=auto_commit)
                        return cached_output
                return self._enqueue_external_classification(db, transaction, provider_override, auto_commit)
            try:
                output = self._classify_with_provider(
                    db, transaction, user_id, provider_override, auto_commit=auto_commit, force_refresh=force_refresh
                )
                if output.category_id is not None:
                    return output
                return self._rule_fallback(
                    db,
                    transaction,
                    user_id,
                    f"{provider_override} returned no valid category",
                    auto_commit=auto_commit,
                )
            except Exception as exc:
                queued = self._queue_for_retry(db, transaction, provider_override, exc, auto_commit)
                if queued is not None:
                    return queued
                if self._is_retryable_external_error(exc):
                    return self._mark_retry_failed(db, transaction, provider_override, exc, auto_commit)
                return self._rule_fallback(
                    db,
                    transaction,
                    user_id,
                    f"{provider_override} failed: {exc}",
                    auto_commit=auto_commit,
                )

        if enqueue_external:
            if not force_refresh:
                cached_output = self._cached_output(db, user_id, transaction, DEFAULT_EXTERNAL_PROVIDER)
                if cached_output is not None:
                    self._store_result(db, transaction, cached_output, auto_commit=auto_commit)
                    return cached_output
            return self._enqueue_external_classification(db, transaction, DEFAULT_EXTERNAL_PROVIDER, auto_commit)

        try:
            model_output = self._classify_with_provider(
                db, transaction, user_id, DEFAULT_EXTERNAL_PROVIDER, auto_commit=auto_commit, force_refresh=force_refresh
            )
            if model_output.category_id is not None:
                return model_output
        except Exception as exc:
            queued = self._queue_for_retry(db, transaction, DEFAULT_EXTERNAL_PROVIDER, exc, auto_commit)
            if queued is not None:
                return queued
            if self._is_retryable_external_error(exc):
                return self._mark_retry_failed(db, transaction, DEFAULT_EXTERNAL_PROVIDER, exc, auto_commit)
            fallback_reason = f"external api failed: {exc}"
        else:
            fallback_reason = "external api returned no valid category"

        return self._rule_fallback(db, transaction, user_id, fallback_reason, auto_commit=auto_commit)

    def _lookup_cache(self, db: Session, user_id: int, transaction: Transaction, provider_name: str) -> ClassificationCache | None:
        text_hash = build_classification_hash(transaction.merchant, transaction.item, transaction.note, transaction.type)
        return db.scalar(
            select(ClassificationCache).where(
                ClassificationCache.user_id == user_id,
                ClassificationCache.provider == provider_name,
                ClassificationCache.text_hash == text_hash,
            )
        )

    def _save_cache(
        self,
        db: Session,
        user_id: int,
        transaction: Transaction,
        output: ClassificationOutput,
        auto_commit: bool = True,
    ) -> None:
        text_hash = build_classification_hash(transaction.merchant, transaction.item, transaction.note, transaction.type)
        existing = db.scalar(
            select(ClassificationCache).where(
                ClassificationCache.user_id == user_id,
                ClassificationCache.provider == output.provider,
                ClassificationCache.text_hash == text_hash,
            )
        )
        if existing is not None:
            return

        cache = ClassificationCache(
            user_id=user_id,
            provider=output.provider,
            text_hash=text_hash,
            category_id=output.category_id,
            subcategory_name=output.subcategory_name,
            confidence=Decimal(str(output.confidence)),
            reason=output.reason,
            raw_response=output.raw_response,
        )
        try:
            with db.begin_nested():
                db.add(cache)
                db.flush()
        except IntegrityError:
            pass
        if auto_commit:
            db.commit()

    def _store_result(
        self,
        db: Session,
        transaction: Transaction,
        output: ClassificationOutput,
        auto_commit: bool = True,
    ) -> None:
        transaction.auto_category_id = output.category_id
        transaction.auto_subcategory_name = output.subcategory_name
        transaction.auto_confidence = Decimal(str(output.confidence))
        transaction.auto_provider = output.provider
        transaction.auto_reason = output.reason
        if output.provider != RETRY_QUEUE_PROVIDER:
            transaction.api_retry_provider = None
        transaction.needs_review = output.confidence < settings.low_confidence_threshold or output.category_id is None
        result = ClassificationResult(
            transaction_id=transaction.id,
            category_id=output.category_id,
            subcategory_name=output.subcategory_name,
            confidence=Decimal(str(output.confidence)),
            reason=output.reason,
            provider=output.provider,
            prompt_version=PROMPT_VERSION,
            raw_response=output.raw_response,
        )
        db.add(result)
        if auto_commit:
            db.commit()


def classify_transaction(
    db: Session,
    transaction: Transaction,
    user_id: int,
    provider_override: str | None = None,
    auto_commit: bool = True,
    *,
    force_refresh: bool = False,
    enqueue_external: bool = True,
) -> ClassificationOutput:
    if provider_override == "rule":
        result = RuleBasedClassifier().classify(db, transaction, user_id)
        if result is None:
            result = ClassificationOutput(None, None, 0.0, "no rule matched", "rule")
        CompositeClassifier()._store_result(db, transaction, result, auto_commit=auto_commit)
        return result
    if provider_override in EXTERNAL_MODEL_PROVIDERS:
        return CompositeClassifier().classify(
            db,
            transaction,
            user_id,
            provider_override=provider_override,
            auto_commit=auto_commit,
            force_refresh=force_refresh,
            enqueue_external=enqueue_external,
        )
    if settings.classification_provider == "local_model":
        return CompositeClassifier().classify(
            db,
            transaction,
            user_id,
            provider_override="local_model",
            auto_commit=auto_commit,
            force_refresh=force_refresh,
            enqueue_external=enqueue_external,
        )
    return CompositeClassifier().classify(
        db,
        transaction,
        user_id,
        provider_override=None,
        auto_commit=auto_commit,
        force_refresh=force_refresh,
        enqueue_external=enqueue_external,
    )
