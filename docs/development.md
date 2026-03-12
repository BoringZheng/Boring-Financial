# 开发文档

## 1. 本地开发环境

建议环境：

- Python 3.11+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+
- Docker / Docker Compose

## 2. 后端启动

```bash
cd backend
pip install -e .[dev]
copy .env.example .env
alembic upgrade head
uvicorn backend.main:app --reload
```

说明：

- 当前代码在应用启动时也会自动 `create_all`，便于快速跑通
- 若要严格控制模式，建议后续补齐正式 Alembic migration

## 3. 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 4. 一键容器开发

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev-up.ps1 -Build
```

## 5. 环境变量

后端关键变量：

- `DATABASE_URL`
- `REDIS_URL`
- `CLASSIFICATION_PROVIDER`
- `OPENAI_API_BASE`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `LOCAL_MODEL_API_BASE`
- `LOCAL_MODEL_API_KEY`
- `LOCAL_MODEL_NAME`
- `LOW_CONFIDENCE_THRESHOLD`
- `TASK_ALWAYS_EAGER`

## 6. 数据库迁移

已包含 Alembic 基础结构：

```bash
cd backend
alembic upgrade head
alembic revision -m "your message"
```

当前仓库更偏课程项目骨架，若继续迭代，建议第一时间补正式 migration 文件。

## 7. 测试与调试

```bash
cd backend
pytest
```

当前提供了基础单元测试：

- `tests/test_security.py`
- `tests/test_normalizers.py`

调试建议：

- 导入问题优先查看 `uploaded_files.error_message`
- 模型问题优先查看 `classification_results.raw_response`
- PDF 问题优先查看 `backend/storage/reports/`

## 8. 常见问题

### PowerShell 无法执行 npm

请使用 `npm.cmd`，或临时绕过执行策略。

### 本地没有 GPU

可以先使用 `infra/model-service/app.py` 的 mock provider 联调，再在云服务器切到 vLLM。

### 账单解析失败

先检查导出文件是否为原始账单格式；当前只支持微信和支付宝导出格式。
