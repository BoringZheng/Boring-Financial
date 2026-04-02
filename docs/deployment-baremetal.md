# 裸机部署文档

目标：

- Debian / Ubuntu 宿主机直接运行 FastAPI 后端
- 前端编译为静态文件，由 Nginx 提供
- 公网入口统一由 Nginx 暴露
- 默认不依赖 Docker

## 1. 推荐部署形态

```text
browser -> nginx:80 -> /      -> frontend/dist
browser -> nginx:80 -> /api/* -> 127.0.0.1:8000
browser -> nginx:80 -> /health -> 127.0.0.1:8000/health
```

说明：

- 后端只监听 `127.0.0.1:8000`
- 公网不直接暴露 8000
- 静态资源不要放在 `/root/...`
- 推荐部署目录：`/opt/Boring-Financial`

## 2. 系统依赖

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm nginx fonts-noto-cjk
```

## 3. 获取代码

```bash
cd /opt
git clone <your-repo-url> Boring-Financial
cd /opt/Boring-Financial
```

## 4. 初始化项目

```bash
bash scripts/setup-baremetal.sh
```

该脚本会：

1. 选择 Python 3.11+
2. 创建 `backend/.venv`
3. 安装后端依赖
4. 构建前端静态资源到 `frontend/dist`

## 5. 配置后端环境变量

```bash
cp backend/.env.bare.example backend/.env
```

至少修改：

- `APP_ENV=prod`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `CORS_ORIGINS`

推荐最小配置：

```env
DATABASE_URL=sqlite:///./storage/app.db
TASK_ALWAYS_EAGER=true
```

## 6. systemd 服务

参考模板：

- `infra/systemd/boring-financial-backend.service`

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

部署命令：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now boring-financial-backend
sudo systemctl status boring-financial-backend
```

## 7. Nginx 配置

参考模板：

- `infra/nginx/boring-financial.bare.conf`

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

## 9. 常见问题

### 9.1 首页 500，但 `/health` 正常

高概率原因：

- Nginx 无法读取前端静态资源
- `root` 指向错误
- 静态资源放在 `/root/...`

处理：

- 把静态资源迁到 `/opt/Boring-Financial/frontend/dist`

### 9.2 systemd 报 `203/EXEC`

处理：

- 不直接运行 `uvicorn`
- 改为 `python -m uvicorn`

### 9.3 systemd 报 `217/USER`

处理：

- 检查服务用户是否存在
- 检查该用户是否有权限访问部署目录

### 9.4 `cors_origins` 解析失败

处理：

- 检查 `CORS_ORIGINS` 写法
- 支持逗号分隔字符串或 JSON 数组

## 10. 更新发布

```bash
cd /opt/Boring-Financial
git pull --ff-only
bash scripts/setup-baremetal.sh
sudo systemctl restart boring-financial-backend
sudo systemctl reload nginx
```
