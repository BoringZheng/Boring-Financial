# 部署文档

## 1. 先同步到 GitHub

当前仓库已经配置好远程：

- `origin -> https://github.com/BoringZheng/Boring-Financial.git`

建议先在本地完成一次干净提交，再推送：

```bash
git status
git add .gitignore .dockerignore README.md backend docs frontend infra legacy scripts output/.gitkeep
git rm --cached -r .obsidian __pycache__ input output
git commit -m "chore: prepare repo for github and ubuntu deployment"
git push origin main
```

说明：

- `git rm --cached` 只会把敏感账单、运行产物和 Obsidian 配置从版本控制里移除，不会删除你本地文件
- `input/.gitkeep` 与 `output/.gitkeep` 会保留空目录结构

## 2. Ubuntu 22.04 服务器准备

最低建议：

- Ubuntu 22.04
- 4 vCPU / 8 GB RAM
- 开放 `80` 端口
- 若部署 vLLM，需要 NVIDIA GPU、驱动和 `nvidia-container-toolkit`

仓库内提供了安装脚本：

```bash
sudo bash scripts/bootstrap-ubuntu2204.sh
sudo usermod -aG docker $USER
newgrp docker
```

## 3. 在服务器拉取 GitHub 仓库

```bash
sudo mkdir -p /opt
sudo chown $USER:$USER /opt
cd /opt
git clone https://github.com/BoringZheng/Boring-Financial.git
cd Boring-Financial
```

如果仓库是私有的，先在服务器配置 GitHub SSH Key，或者使用 PAT。

## 4. 配置服务器环境变量

```bash
cp infra/.env.example infra/.env.server
```

至少修改这些值：

- `POSTGRES_PASSWORD`
- `OPENAI_API_KEY`，如果你要走 OpenAI API
- `CORS_ORIGINS`，改成你的域名
- `LOCAL_MODEL_NAME`，如果你不用默认 mock 服务

默认端口绑定已经收紧到本机回环地址：

- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Backend: `127.0.0.1:8000`
- Frontend: `127.0.0.1:4173`
- Model service: `127.0.0.1:8001`
- Nginx: `0.0.0.0:80`

这意味着公网默认只暴露 Nginx。

## 5. 启动服务

### 5.1 CPU / mock model

```bash
bash scripts/deploy-ubuntu.sh
```

### 5.2 GPU / vLLM

```bash
bash scripts/deploy-ubuntu.sh --with-vllm
```

部署脚本会：

1. 检查 `docker` 和 `docker compose`
2. 自动 `git pull --ff-only`
3. 使用 `infra/.env.server` 启动容器
4. 输出当前容器状态

## 6. 常用运维命令

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

如果启用了 vLLM，把 `-f infra/docker-compose.cloud.yml` 一并带上。

## 7. HTTPS 与域名

当前仓库的 `infra/nginx/nginx.conf` 只处理 HTTP 反向代理。线上要上 HTTPS，建议：

1. 域名解析到服务器公网 IP
2. 宿主机用 Caddy、Nginx 或 Certbot 处理证书
3. 证书终止后再反向代理到容器里的 `nginx:80`

如果你希望证书也放进容器里，可以再补一份 HTTPS 版 Nginx 配置。

## 8. 数据持久化与备份

Compose volumes：

- `postgres-data`
- `backend-storage`

建议定期备份：

```bash
docker volume inspect boring-financial_postgres-data
docker volume inspect boring-financial_backend-storage
```

另外，`backend-storage` 里会保存上传文件和生成报表，不要只备份数据库。
