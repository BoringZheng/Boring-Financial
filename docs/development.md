# 开发文档

## 1. 面向读者

本文档面向接手本仓库的开发者，目标是帮助你快速完成：

- 理解 monorepo 结构和模块职责。
- 使用 `uv` 启动后端开发环境。
- 启动 Vue 3 前端并完成前后端联调。
- 定位常见开发问题。

## 2. 仓库结构

```text
backend/   FastAPI 后端、SQLAlchemy 模型、分类服务、报表生成、测试
frontend/  Vue 3 + Vite 前端
infra/     Docker Compose、Nginx、systemd、mock model service
docs/      架构、接口、开发、部署、测试文档
legacy/    旧版脚本
scripts/   本地开发与部署辅助脚本
```

关键目录：

- `backend/pyproject.toml`: 后端包元数据和依赖声明。
- `backend/uv.lock`: 后端依赖锁文件，开发安装以它为准。
- `backend/src/backend/api/`: HTTP 路由和 JWT 鉴权依赖。
- `backend/src/backend/services/`: 核心业务逻辑，含启动引导（`bootstrap.py`）自动初始化默认分类和规则种子。
- `backend/src/backend/models/`: SQLAlchemy 数据模型。
- `backend/src/backend/schemas/`: Pydantic 请求/响应模型。
- `backend/src/backend/tasks/`: Celery 任务入口。
- `frontend/src/layouts/`: 应用级布局。
- `frontend/src/pages/`: 页面级组件。
- `frontend/src/api/client.ts`: Axios API 客户端。

## 3. 技术栈

后端：

- Python 3.11+
- uv
- FastAPI
- SQLAlchemy 2.x
- Pydantic Settings
- Alembic
- Celery + Redis
- fpdf2
- pytest

前端：

- Node.js 20+
- npm
- Vue 3
- Vite 7
- TypeScript
- Pinia
- Vue Router
- Element Plus
- ECharts

## 4. 后端本地开发

后端使用 `uv` 管理依赖和虚拟环境。不要手动写 `pip install -e ".[dev]"` 作为常规启动方式。

### 4.1 安装 uv

确认本机已安装：

```bash
uv --version
```

如果没有安装，按 uv 官方文档安装后再继续。

### 4.2 轻量 SQLite 启动

适合课程 demo、本地快速验收和低配机器。

PowerShell:

```powershell
cd backend
Copy-Item .env.bare.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

Bash:

```bash
cd backend
cp .env.bare.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

`.env.bare.example` 默认使用：

```env
DATABASE_URL=sqlite:///./storage/app.db
TASK_ALWAYS_EAGER=true
```

应用启动时会创建运行期表和默认分类。

### 4.3 PostgreSQL + Redis 启动

先从仓库根目录启动依赖：

```bash
cd infra
docker compose up -d postgres redis
```

再启动后端。

PowerShell:

```powershell
cd ..\backend
Copy-Item .env.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

Bash:

```bash
cd ../backend
cp .env.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

### 4.4 常用后端命令

```bash
uv run pytest
uv run pytest --cov=backend
uv run alembic upgrade head
uv run celery -A backend.core.celery_app.celery_app worker -l info
uv run bf-admin retry-all
uv run bf-admin retry-all --user-id <id>
uv run bf-admin make-admin <username>
```

说明：当前本地快速启动不强制要求 Alembic migration，因为 `backend.main` 的 lifespan 会调用 SQLAlchemy metadata 创建运行期表。Alembic 保留给后续正式迁移版本管理。

外部模型请求默认进入统一 `retry_queue`，由后端 lifespan 中启动的后台 worker 串行发送。开发时如果看到交易来源为 `retry_queue`，表示等待后台处理；`retry_failed` 表示超时重试耗尽。管理员可在设置页点击“一键重试历史超时”，或运行 `uv run bf-admin retry-all`。首次使用后台管理员按钮前，运行 `uv run bf-admin make-admin <username>`。

## 5. 前端本地开发

### 5.1 安装依赖

```bash
cd frontend
npm install
```

### 5.2 启动开发服务器

Windows PowerShell 推荐：

```powershell
npm.cmd run dev
```

Bash:

```bash
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

前端代理：

```text
/api -> http://127.0.0.1:8000
```

### 5.3 构建前端

```bash
npm.cmd run build
```

非 Windows：

```bash
npm run build
```

## 6. 前端设计约定

当前前端采用专业后台系统风格：

- 深色侧边栏：`#06233D` / `#041A2E`
- 主色：`#00A884`
- 页面背景：`#F5F7FA`
- 卡片背景：`#FFFFFF`
- 卡片圆角：8px
- 图表：ECharts
- 基础组件：Element Plus

页面统一使用 `.page-shell`、`.page-heading`、`.panel`、`.card` 等全局样式。新增页面应优先复用现有样式和 Element Plus 组件。

## 7. 开发注意事项

- 后端依赖变更后，更新 `backend/pyproject.toml` 并重新生成 `backend/uv.lock`。
- 不要绕过 `uv.lock` 手动维护后端依赖环境。
- 不要改动后端接口路径，除非同步更新 `docs/api.md` 和前端调用。
- 低配服务器优先，避免高频模型调用和大规模全量查询。
- 文档、页面文案和代码注释统一使用 UTF-8。

## 8. 常见问题

### PowerShell 无法运行 npm

使用：

```powershell
npm.cmd run dev
npm.cmd run build
```

### Vite 报 `spawn EPERM`

通常是本机或沙箱限制阻止 esbuild 子进程启动。确认 Node.js 安装正常，并在允许子进程的终端中运行。

### 前端请求 401

检查：

- 是否已登录。
- `localStorage` 中是否存在 `bf_access_token`。
- 后端 `SECRET_KEY` 是否变化导致旧 token 失效。

### 导入任务一直处理中

检查：

- `TASK_ALWAYS_EAGER` 配置。
- Redis/Celery worker 是否运行。
- 后端日志中是否有文件解析或模型调用错误。
