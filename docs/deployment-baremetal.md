# 裸机部署文档

目标：

- Ubuntu 22.04 宿主机直接运行 FastAPI 后端
- 前端编译成静态文件，由宿主机 Nginx 提供
- 公网机器通过同一个域名或 IP 访问
- 默认不使用 Docker

## 1. 推荐架构

```text
browser -> nginx:80 -> /      -> frontend/dist
browser -> nginx:80 -> /api/* -> 127.0.0.1:8000
browser -> nginx:80 -> /health -> 127.0.0.1:8000/health
```

后端只监听 `127.0.0.1:8000`，不直接暴露公网。

## 2. 服务器安装依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx
```

如果你需要 PDF 中文字体，额外安装：

```bash
sudo apt install -y fonts-noto-cjk
```

## 3. 初始化项目

仓库根目录执行：

```bash
bash scripts/setup-baremetal.sh
```

这个脚本会：

1. 创建 `backend/.venv`
2. 安装后端依赖
3. 生成 `backend/.env`
4. 执行前端 `npm ci` 和 `npm run build`

## 4. 配置后端环境变量

复制模板：

```bash
cp backend/.env.bare.example backend/.env
```

至少修改：

- `SECRET_KEY`
- `OPENAI_API_KEY`
- `CORS_ORIGINS`

默认使用 SQLite：

```env
DATABASE_URL=sqlite:///./storage/app.db
TASK_ALWAYS_EAGER=true
```

这意味着你不需要额外安装 PostgreSQL 和 Redis 就能先跑起来。

## 5. 后端 systemd 服务

模板文件：

- `infra/systemd/boring-financial-backend.service`

使用前先改两处：

1. `User` / `Group`
2. `WorkingDirectory` / `EnvironmentFile` / `ExecStart`

示例命令：

```bash
sudo cp infra/systemd/boring-financial-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now boring-financial-backend
sudo systemctl status boring-financial-backend
```

## 6. Nginx 提供静态页并反代 API

模板文件：

- `infra/nginx/boring-financial.bare.conf`

使用前先改：

1. `root` 为你的前端静态目录
2. `server_name` 为你的域名或 `_`

示例命令：

```bash
sudo cp infra/nginx/boring-financial.bare.conf /etc/nginx/sites-available/boring-financial
sudo ln -sf /etc/nginx/sites-available/boring-financial /etc/nginx/sites-enabled/boring-financial
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 验证

后端健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://YOUR_SERVER_IP/health
```

前端静态页：

```bash
curl http://YOUR_SERVER_IP/
```

## 8. 更新发布

每次代码更新后：

```bash
git pull --ff-only
bash scripts/setup-baremetal.sh
sudo systemctl restart boring-financial-backend
sudo systemctl reload nginx
```

## 9. 关键注意点

- 前端现在默认请求同源 `/api`，适合 Nginx 同域部署
- PDF 报表生成已经增加 Ubuntu 字体 fallback，但服务器最好安装 `fonts-noto-cjk`
- 如果后续访问量上来，再把 SQLite 换成 PostgreSQL
