# 开发者文档

## 1. Who should read this

本文档面向接手本仓库的开发者，目标是让你在不依赖额外说明的情况下完成以下事务：

- 理解仓库结构与主要模块职责
- 在本地启动前后端并联调
- 了解当前项目在开发态和裸机部署态的差异
- 快速定位常见问题

## 2. 仓库结构

```text
backend/   FastAPI 后端、数据库模型、分类逻辑、报表生成、测试
frontend/  Vue 3 + Vite 前端
infra/     Docker Compose、Nginx、systemd、模型服务模板
docs/      架构、接口、开发、部署、测试文档
legacy/    旧版脚本
scripts/   本地开发与裸机部署辅助脚本
```

关键目录：

- `backend/src/backend/api/`：HTTP 路由层
- `backend/src/backend/services/`：核心业务逻辑
- `backend/src/backend/models/`：SQLAlchemy 模型
- `backend/src/backend/core/`：配置、安全、Celery 配置
- `frontend/src/pages/`：页面级组件
- `frontend/src/api/client.ts`：统一 API 客户端

## 3. 技术栈与当前实现取向

后端：

- FastAPI
- SQLAlchemy 2.x
- Pydantic Settings
- Alembic
- `fpdf2`

前端：

- Vue 3
- Vite 7
- TypeScript
- Pinia
- Vue Router
- Element Plus

## 4. 开发环境要求

建议：

- Python 3.11+
- Node.js 20+
- npm 10+

可选：

- PostgreSQL 16+
- Redis 7+
- Docker / Docker Compose

Windows 开发建议：

- 使用 PowerShell
- 如果 `npm` 被执行策略拦截，改用 `npm.cmd`

## 5. 后端本地开发

### 5.1 创建虚拟环境

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 5.2 安装依赖

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 5.3 准备环境变量

开发环境模板：

```bash
copy .env.example .env
```

或：

```bash
cp .env.example .env
```

最关键的几个变量：

- `DATABASE_URL`
- `CLASSIFICATION_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TASK_ALWAYS_EAGER`
- `CORS_ORIGINS`

开发机如果只想先跑通，不想装 PostgreSQL，可以把：

```env
DATABASE_URL=sqlite:///./storage/app.db
TASK_ALWAYS_EAGER=true
```

### 5.4 启动后端

```bash
uvicorn backend.main:app --reload
```

默认健康检查：

```text
http://127.0.0.1:8000/health
```

## 6. 前端本地开发

### 6.1 安装依赖

```bash
cd frontend
npm install
```

### 6.2 启动开发服务器

```bash
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

当前前端开发代理已经配置为：

- `/api` -> `http://127.0.0.1:8000`

这意味着本地联调时只要后端跑在 8000 端口即可。

## 7. 开发者须知

如果你想对本项目做出贡献，你应当：
1. 从main branch fork一个分支，并只在你的分支上进行改动。
2. 你应当只改动\backend \docs \frontend 中的文件。
3. 你应当参照README.md中的文件索引，对于你的改动在对应的文档中做出说明。
4. 如果你已经测试完成你的分支并认为其可以上线，那么你应当提一个pull request而非直接commit to main branch。