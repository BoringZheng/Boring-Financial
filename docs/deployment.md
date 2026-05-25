# Docker 部署文档

本文档说明如何使用 Docker Compose 部署 Boring Financial。低配服务器也可以参考 [裸机部署文档](./deployment-baremetal.md)，减少容器数量。

## 1. 服务组成

`infra/docker-compose.yml` 包含：

- `postgres`: PostgreSQL 16
- `redis`: Redis 7
- `backend`: FastAPI 后端
- `worker`: Celery worker
- `frontend`: 前端静态站点
- `model-service`: mock OpenAI-compatible 模型服务
- `nginx`: 统一入口，代理前端和 `/api`

后端镜像构建会复制 `backend/uv.lock`，并在镜像内执行 `uv sync --frozen --no-dev`，因此容器依赖版本与锁文件保持一致。

默认入口：

```text
browser -> nginx:80 -> frontend
browser -> nginx:80/api -> backend:8000
```

## 2. 服务器准备

推荐环境：

- Ubuntu 22.04 或 Debian 12
- 2 vCPU / 4 GB RAM 可跑课程 demo
- 4 vCPU / 8 GB RAM 更适合同时运行 PostgreSQL、Redis、worker 和 mock model
- 开放 `80` 端口
- 已安装 Docker 和 Docker Compose

仓库提供基础脚本：

```bash
sudo bash scripts/bootstrap-ubuntu2204.sh
sudo usermod -aG docker $USER
newgrp docker
```

## 3. 获取代码

```bash
cd /opt
git clone https://github.com/BoringZheng/Boring-Financial.git
cd Boring-Financial
```

如果仓库为私有仓库，请先配置 SSH key 或 PAT。

## 4. 配置环境变量

```bash
cp infra/.env.example infra/.env.server
```

至少检查以下变量：

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `SECRET_KEY`：JWT 签名密钥，生产环境务必修改。注意 `infra/.env.example` 不包含此项，需手动添加到 `.env.server` 并在 `docker-compose.yml` 的 `backend` 和 `worker` 服务中引用（默认 `docker-compose.yml` 未传递此变量，后端使用硬编码默认值 `change-me`）。
- `OPENAI_API_KEY`
- `CLASSIFICATION_PROVIDER`
- `CORS_ORIGINS`
- `NGINX_HTTP_PORT`
- `TASK_ALWAYS_EAGER`

低配服务器建议：

```env
TASK_ALWAYS_EAGER=true
CLASSIFICATION_PROVIDER=composite
```

如暂时不接真实模型，可保持 mock `model-service`。

外部模型请求由 `backend` 服务中的 retry queue worker 统一串行发送，不由用户请求线程或导入线程并发发送。生产环境如果水平扩展多个 `backend` 副本，需要把 retry worker 拆成单独唯一实例或增加数据库锁，否则多个后端进程会形成多个发送者。

管理员运维命令：
```bash
cd backend
uv run bf-admin make-admin <username>
uv run bf-admin retry-all
uv run bf-admin retry-all --user-id <id>
```

## 5. 启动服务

CPU / mock model 部署：

```bash
bash scripts/deploy-ubuntu.sh
```

手动启动：

```bash
cd infra
docker compose --env-file .env.server up --build -d
```

查看状态：

```bash
docker compose --env-file infra/.env.server -f infra/docker-compose.yml ps
```

查看日志：

```bash
docker compose --env-file infra/.env.server -f infra/docker-compose.yml logs -f backend worker nginx
```

停止服务：

```bash
docker compose --env-file infra/.env.server -f infra/docker-compose.yml down
```

## 6. GPU / vLLM 部署

如果服务器有 NVIDIA GPU，可叠加 `infra/docker-compose.cloud.yml`：

```bash
bash scripts/deploy-ubuntu.sh --with-vllm
```

使用 vLLM 前需确认：

- NVIDIA driver 已安装。
- `nvidia-container-toolkit` 已配置。
- `LOCAL_MODEL_NAME` 与模型服务一致。
- `LOCAL_MODEL_API_BASE` 指向 vLLM OpenAI-compatible 地址。

## 7. 端口说明

默认端口绑定可通过 `.env.server` 调整：

- PostgreSQL: `POSTGRES_PORT_BIND`
- Redis: `REDIS_PORT_BIND`
- Backend: `BACKEND_PORT_BIND`
- Frontend: `FRONTEND_PORT_BIND`
- Model service: `MODEL_SERVICE_PORT_BIND`
- Nginx: `NGINX_HTTP_PORT`

生产建议只暴露 Nginx，数据库、Redis、后端和模型服务绑定本机或内网。

## 8. 数据持久化

Compose volumes：

- `postgres-data`: PostgreSQL 数据。
- `backend-storage`: 上传文件和生成报表。

备份时不要只备份数据库，也要备份 `backend-storage`，否则历史上传文件和 PDF 报表会丢失。

## 9. HTTPS 和域名

当前 `infra/nginx/nginx.conf` 只处理 HTTP。生产环境建议：

1. 域名解析到服务器公网 IP。
2. 使用 Caddy、宿主机 Nginx 或 Certbot 处理 TLS。
3. TLS 终止后反向代理到容器中的 Nginx `80` 端口。

## 10. 更新发布

```bash
cd /opt/Boring-Financial
git pull --ff-only
bash scripts/deploy-ubuntu.sh
```

发布后验证：

```bash
curl http://127.0.0.1/health
curl http://127.0.0.1/
```

浏览器访问：

```text
http://YOUR_SERVER_IP/
```
