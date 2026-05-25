# 外部 API 超时交易自动重试池 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导入或重分类时外部 API 超时的交易不直接丢给用户手动处理，而是放入重试池由后台 worker 逐个重试；同时提供管理命令一键将历史超时交易推入池子。

**Architecture:** 新增 `api_retry_count` 字段跟踪重试次数。`CompositeClassifier.classify()` 在 API 异常时检查计数：未达上限则标记 `retry_queue` 隐藏，超过上限才走原有规则回退。后台 daemon 线程轮询 retry_queue 逐个重试。管理 CLI 通过 `pyproject.toml` 注册 `[project.scripts]` 入口。

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, FastAPI, Threading

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/src/backend/models/entities.py` | 新增 `api_retry_count` 列 |
| `backend/src/backend/core/config.py` | 新增重试池相关配置 |
| `backend/src/backend/services/classifiers.py` | 修改 `CompositeClassifier.classify()` 异常处理，API 失败时判断是否入池 |
| `backend/src/backend/services/imports.py` | 删除上一版内联重试代码 |
| `backend/src/backend/services/retry_queue.py` | **新建** — 后台 worker + 存量迁移函数 + "全部重入池"函数 |
| `backend/src/backend/main.py` | lifespan 中：补列 + 迁移存量 + 启动 worker |
| `backend/src/backend/cli.py` | **新建** — 管理 CLI：`bf-admin retry-all` 命令 |
| `backend/pyproject.toml` | 注册 `[project.scripts]` 入口 |
| `frontend/src/pages/TransactionsPage.vue` | `providerText()` 添加 `retry_queue` 中文标签 |
| `frontend/src/pages/ReviewPage.vue` | `providerText()` 添加 `retry_queue` 中文标签 |

---

### Task 1: 新增配置项

**Files:**
- Modify: `backend/src/backend/core/config.py`

- [ ] **Step 1: 在 Settings 类中添加配置字段**

在 `low_confidence_threshold` (第 36 行) 之后添加：

```python
# Retry queue settings — api failures during import / reclassify are queued
# and retried one-at-a-time by a background thread.
retry_queue_max_retries: int = 5
retry_queue_delay_seconds: float = 5.0
retry_queue_poll_seconds: float = 15.0
```

- [ ] **Step 2: 验证配置可加载**

```bash
cd backend && uv run python -c "from backend.core.config import settings; print(settings.retry_queue_max_retries)"
```
Expected: `5`

---

### Task 2: 新增 Transaction 字段

**Files:**
- Modify: `backend/src/backend/models/entities.py`

- [ ] **Step 1: 在 Transaction 类中添加 api_retry_count**

在 `needs_review` (第 116 行) 之后添加：

```python
api_retry_count: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: 验证字段定义**

```bash
cd backend && uv run python -c "from backend.models.entities import Transaction; print(hasattr(Transaction, 'api_retry_count'))"
```
Expected: `True`

---

### Task 3: 运行时补齐数据库列

**Files:**
- Modify: `backend/src/backend/main.py`

- [ ] **Step 1: 在 ensure_runtime_schema 中添加 api_retry_count 列检测**

修改 `ensure_runtime_schema()` 函数，在现有 `total_count` 检查后添加：

```python
if "transactions" in inspector.get_table_names():
    txn_columns = {column["name"] for column in inspector.get_columns("transactions")}
    if "api_retry_count" not in txn_columns:
        statements.append("ALTER TABLE transactions ADD COLUMN api_retry_count INTEGER DEFAULT 0 NOT NULL")
```

- [ ] **Step 2: 验证函数语法**

```bash
cd backend && uv run python -c "from backend.main import ensure_runtime_schema; print('OK')"
```
Expected: `OK`

---

### Task 4: 修改 CompositeClassifier 异常处理

**Files:**
- Modify: `backend/src/backend/services/classifiers.py`

- [ ] **Step 1: 导入 settings 和 Decimal**

确认文件顶部已有 `from backend.core.config import settings` 和 `from decimal import Decimal`。如果没有 Decimal 导入则需要添加。（当前 ~18 行有 `from decimal import Decimal`）

- [ ] **Step 2: 添加辅助方法 _queue_for_retry**

在 `CompositeClassifier` 类中，`_rule_fallback` 方法之前添加：

```python
def _queue_for_retry(
    self, db: Session, transaction: Transaction, exc: Exception, auto_commit: bool
) -> ClassificationOutput | None:
    """Queue tx for background retry if under limit. Returns None if limit reached."""
    if transaction.api_retry_count >= settings.retry_queue_max_retries:
        return None
    transaction.api_retry_count += 1
    transaction.auto_provider = "retry_queue"
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
        provider="retry_queue",
        raw_response=None,
    )
```

- [ ] **Step 3: 修改 provider_override 路径的异常处理 (~350行)**

将：
```python
except Exception as exc:
    return self._rule_fallback(
        db, transaction, user_id,
        f"{provider_override} failed: {exc}",
        auto_commit=auto_commit,
    )
```

改为：
```python
except Exception as exc:
    queued = self._queue_for_retry(db, transaction, exc, auto_commit)
    if queued is not None:
        return queued
    return self._rule_fallback(
        db, transaction, user_id,
        f"{provider_override} failed: {exc}",
        auto_commit=auto_commit,
    )
```

- [ ] **Step 4: 修改默认路径的异常处理 (~365行)**

将：
```python
except Exception as exc:
    fallback_reason = f"external api failed: {exc}"
```

改为：
```python
except Exception as exc:
    queued = self._queue_for_retry(db, transaction, exc, auto_commit)
    if queued is not None:
        return queued
    fallback_reason = f"external api failed: {exc}"
```

- [ ] **Step 5: 验证模块加载**

```bash
cd backend && uv run python -c "from backend.services.classifiers import classify_transaction, CompositeClassifier; print('OK')"
```
Expected: `OK`

---

### Task 5: 删除 imports.py 内联重试代码

**Files:**
- Modify: `backend/src/backend/services/imports.py`

- [ ] **Step 1: 删除上一版添加的重试循环**

删除 228 行到 262 行之间的重试循环块（`# Retry transactions where the external API failed` 到 `db.commit()` 在 `db.refresh(batch)` 之前）。恢复为原始的直接设置 batch status 后 commit 并 refresh 的代码：

```python
    db.refresh(batch)
    return batch
```

- [ ] **Step 2: 验证模块加载**

```bash
cd backend && uv run python -c "from backend.services.imports import process_import_batch; print('OK')"
```
Expected: `OK`

---

### Task 6: 新建后台 Worker 及迁移函数

**Files:**
- Create: `backend/src/backend/services/retry_queue.py`

- [ ] **Step 1: 创建 retry_queue.py 模块**

```python
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

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
```

- [ ] **Step 2: 验证模块加载**

```bash
cd backend && uv run python -c "from backend.services.retry_queue import run_retry_queue_worker, migrate_existing_timeouts, requeue_all_external_api_failures; print('OK')"
```
Expected: `OK`

---

### Task 7: 在 lifespan 中集成 Worker + 存量迁移

**Files:**
- Modify: `backend/src/backend/main.py`

- [ ] **Step 1: 修改 lifespan 启动 worker 并迁移存量**

当前 lifespan 函数：

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    yield
```

改为：

```python
import threading

@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()

    # Migrate existing timeout transactions into the retry queue
    from backend.services.retry_queue import migrate_existing_timeouts, run_retry_queue_worker
    migrate_existing_timeouts()

    # Start background retry worker
    stop_event = threading.Event()
    worker = threading.Thread(
        target=run_retry_queue_worker,
        args=(stop_event,),
        daemon=True,
        name="retry-queue-worker",
    )
    worker.start()

    yield

    # Shutdown
    stop_event.set()
```

- [ ] **Step 2: 验证应用启动正常**

```bash
cd backend && timeout 5 uv run uvicorn backend.main:app --port 0 2>&1 || true
```
Expected: 日志中能看到 "Retry queue worker started" 和迁移信息（如果有存量超时交易）

---

### Task 8: 新建管理 CLI

**Files:**
- Create: `backend/src/backend/cli.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 创建 cli.py**

```python
"""Management CLI for Boring Financial.

Commands:
    retry-all   Push all transactions with external-API issues back into
                the retry queue so the background worker retries them.
"""

from __future__ import annotations

import argparse

from backend.core.config import settings
from backend.services.retry_queue import requeue_all_external_api_failures


def cmd_retry_all() -> None:
    """Requeue every transaction whose auto_reason mentions 'external api'."""
    print(f"Database: {settings.database_url}")
    print("Scanning for transactions with external API issues ...")
    count = requeue_all_external_api_failures()
    if count == 0:
        print("No transactions found — nothing to do.")
    else:
        print(
            f"Done — {count} transaction(s) moved to retry queue. "
            f"The background worker will retry them one at a time "
            f"(max {settings.retry_queue_max_retries} retries, "
            f"{settings.retry_queue_delay_seconds}s delay between requests)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bf-admin",
        description="Boring Financial management CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "retry-all",
        help="Push all external-API-failed transactions back to retry queue",
    )

    args = parser.parse_args()

    if args.command == "retry-all":
        cmd_retry_all()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 注册 [project.scripts] 入口**

在 `backend/pyproject.toml` 的 `[project]` section 末尾添加：

```toml
[project.scripts]
bf-admin = "backend.cli:main"
```

- [ ] **Step 3: 安装并验证 CLI**

```bash
cd backend && uv pip install -e . && uv run bf-admin --help
```
Expected: 显示 usage 和 retry-all 子命令

- [ ] **Step 4: 验证 retry-all 命令**

```bash
cd backend && uv run bf-admin retry-all
```
Expected: `No transactions found — nothing to do.` (数据库为空) 或显示迁移数量

---

### Task 9: 前端 providerText 添加中文标签

**Files:**
- Modify: `frontend/src/pages/TransactionsPage.vue`
- Modify: `frontend/src/pages/ReviewPage.vue`

- [ ] **Step 1: TransactionsPage.vue**

在 `providerText` 函数的 map 中添加一行：

```typescript
function providerText(provider: string | null) {
  const map: Record<string, string> = {
    rule: '规则',
    composite: '混合',
    openai_compatible_api: '外部模型',
    local_model: '本地模型',
    retry_queue: '等待重试',
  }
  return provider ? map[provider] ?? provider : '未分类'
}
```

- [ ] **Step 2: ReviewPage.vue**

相同修改：

```typescript
function providerText(provider: string | null) {
  const map: Record<string, string> = {
    rule: '规则',
    composite: '混合分类',
    openai_compatible_api: '外部模型',
    local_model: '本地模型',
    retry_queue: '等待重试',
  }
  return provider ? map[provider] ?? provider : '未分类'
}
```

- [ ] **Step 3: Type check**

```bash
cd frontend && npx vue-tsc --noEmit
```
Expected: clean exit, no errors

---

### Task 10: 端到端验证

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && uv run pytest tests/ -x -q 2>&1
```
Expected: 除已有的 `test_call_model_limits_output_tokens` 外全部通过

- [ ] **Step 2: 确认 worker 启动日志**

启动应用后检查日志中是否出现：
```
Retry queue worker started (max_retries=5, delay=5.0s, poll=15.0s)
Migrated N existing timeout transactions to retry queue
```

- [ ] **Step 3: 模拟超时重试流程**

1. 导入包含交易的账单文件
2. 如果外部 API 超时，交易应标记为 `auto_provider = "retry_queue"`, `needs_review = False`
3. 校正页面不应出现这些交易
4. 等待后台 worker 处理，交易逐步完成分类
5. 运行 `bf-admin retry-all` 可一键将所有历史问题交易推回池子

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/models/entities.py \
        backend/src/backend/core/config.py \
        backend/src/backend/services/classifiers.py \
        backend/src/backend/services/imports.py \
        backend/src/backend/services/retry_queue.py \
        backend/src/backend/main.py \
        backend/src/backend/cli.py \
        backend/pyproject.toml \
        frontend/src/pages/TransactionsPage.vue \
        frontend/src/pages/ReviewPage.vue
git commit -m "feat: add background retry queue for external API timeout transactions

Transactions that time out during import / reclassify are now queued
for retry instead of being immediately shown for manual review. A
background daemon thread retries them one-at-a-time. Admin command
'bf-admin retry-all' pushes all historical timeout transactions back
into the queue.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
