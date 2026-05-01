# 裸机部署文档

本文档说明如何在 Debian / Ubuntu 主机上不使用 Docker 直接部署项目。该方式适合性能较弱的服务器：前端构建为静态文件，后端由 systemd 托管，公网入口统一由 Nginx 暴露。

## 1. 推荐拓扑

```text
browser -> nginx:80 -> /        -> frontend/dist
browser -> nginx:80 -> /api/*   -> 127.0.0.1:8000
browser -> nginx:80 -> /health  -> 127.0.0.1:8000/health
```

建议：

- 后端只监听 `127.0.0.1:8000`。
- 公网不要直接暴露 `8000`。
- 前端静态资源放在 `/opt/Boring-Financial/frontend/dist`。
- 低配服务器可使用 SQLite 和 `TASK_ALWAYS_EAGER=true`。

## 2. 系统依赖

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm nginx fonts-noto-cjk
```

如果系统 Node.js 版本过低，请使用 NodeSource 或 nvm 安装 Node.js 20+。

后端依赖由 `uv` 管理，服务器也需要安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后重新打开 shell，确认：

```bash
uv --version
```

## 3. 获取代码

```bash
sudo mkdir -p /opt
sudo chown $USER:$USER /opt
cd /opt
git clone <your-repo-url> Boring-Financial
cd /opt/Boring-Financial
```

## 4. 初始化项目

仓库提供脚本：

```bash
bash scripts/setup-baremetal.sh
```

脚本职责：

1. 检查 Python 3.11+。
2. 检查 `uv` 和 `npm` 是否可用。
3. 在 `backend/` 中执行 `uv sync --extra dev`，根据 `uv.lock` 创建或更新 `.venv`。
4. 安装前端依赖。
5. 构建前端静态资源到 `frontend/dist`。

## 5. 配置后端环境变量

```bash
cp backend/.env.bare.example backend/.env
```

至少修改：

- `APP_ENV=prod`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `CORS_ORIGINS`

低配服务器推荐：

```env
DATABASE_URL=sqlite:///./storage/app.db
TASK_ALWAYS_EAGER=true
CLASSIFICATION_PROVIDER=composite
```

如使用 PostgreSQL，请将 `DATABASE_URL` 改为 PostgreSQL 连接串。

## 6. systemd 服务

参考模板：

```text
infra/systemd/boring-financial-backend.service
```

推荐内容：

```ini
[Unit]
Description=Boring Financial FastAPI Backend
After=network.target

[Service]
Type=simple
User=boring
Group=boring
WorkingDirectory=/opt/Boring-Financial/backend
EnvironmentFile=/opt/Boring-Financial/backend/.env
ExecStart=/opt/Boring-Financial/backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now boring-financial-backend
sudo systemctl status boring-financial-backend
```

## 7. Nginx 配置

参考模板：

```text
infra/nginx/boring-financial.bare.conf
```

推荐站点配置：

```nginx
server {
  listen 80;
  server_name _;

  root /opt/Boring-Financial/frontend/dist;
  index index.html;
  client_max_body_size 50m;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /health {
    proxy_pass http://127.0.0.1:8000/health;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

启用配置：

```bash
sudo cp infra/nginx/boring-financial.bare.conf /etc/nginx/sites-available/boring-financial
sudo ln -sf /etc/nginx/sites-available/boring-financial /etc/nginx/sites-enabled/boring-financial
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## 8. 验证

服务器本机：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
curl http://127.0.0.1/
```

外部机器：

```bash
curl http://YOUR_SERVER_IP/health
curl http://YOUR_SERVER_IP/
```

浏览器访问：

```text
http://YOUR_SERVER_IP/
```

## 9. 常见问题

### 首页 500，但 `/health` 正常

常见原因：

- Nginx 无法读取前端静态资源。
- `root` 指向错误。
- 静态资源放在 `/root/...` 导致权限不足。

处理：

- 确认 `frontend/dist/index.html` 存在。
- 将项目部署在 `/opt/Boring-Financial`。
- 确认 Nginx worker 用户可读静态资源。

### systemd 报 `203/EXEC`

处理：

- 不要直接运行 `uvicorn`。
- 使用 `python -m uvicorn backend.main:app ...`。
- 确认虚拟环境路径正确。

### systemd 报 `217/USER`

处理：

- 确认服务配置中的 `User` 和 `Group` 存在。
- 确认该用户有权限访问 `/opt/Boring-Financial`。

### CORS 配置错误

处理：

- 检查 `CORS_ORIGINS` 写法。
- 支持逗号分隔字符串或 JSON 数组。
- 生产环境应包含实际域名或服务器地址。

## 10. 更新发布

```bash
cd /opt/Boring-Financial
git pull --ff-only
bash scripts/setup-baremetal.sh
sudo systemctl restart boring-financial-backend
sudo systemctl reload nginx
```
