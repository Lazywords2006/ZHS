# ZHS

一个基于 Python 的智慧树自动化项目，当前仓库包含两部分：

- 根目录 CLI：原始刷课脚本与接口封装
- `web-demo/`：Vue 3 + Element Plus 管理面板，已接入真实 Python 后端

当前前端支持：

- 多账号新增、删除
- 二维码登录
- 课程列表拉取
- 单课观看时长开关，默认一直观看
- 每日自动执行开关、天数输入与截止日期展示
- 任务启动、停止、状态轮询
- 本地保存登录态，并在后端重启后自动尝试恢复

## 目录结构

```text
.
├── main.py                  # 原始 CLI 入口
├── fucker.py                # 核心业务逻辑
├── utils.py                 # 通用工具
├── zd_utils.py              # 知到相关加密/观看点工具
├── sign.py                  # Hike 接口签名
├── decrypt/                 # 逆向辅助脚本
└── web-demo/
    ├── src/                 # Vue 3 前端
    ├── backend/
    │   ├── app.py           # FastAPI 示例后端
    │   └── runtime/         # 运行时账号配置与登录态
    └── dist/                # 前端构建产物
```

## 环境要求

- Linux x86_64 / arm64
- Python 3.11+
- Node.js 18+
- npm 9+

根目录代码使用了 `match/case`，Python 3.10 以下不能运行。建议直接使用 Python 3.11 或更高版本。

## 本地快速启动

### 1. 安装根目录 Python 依赖

```bash
cd /path/to/ZHS
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r web-demo/backend/requirements.txt
```

### 2. 启动后端

```bash
cd /path/to/ZHS/web-demo/backend
source ../../.venv/bin/activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### 3. 启动前端开发环境

```bash
cd /path/to/ZHS/web-demo
cp .env.example .env.local
```

编辑 `web-demo/.env.local`：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

然后启动前端：

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

默认访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## CLI 用法

根目录脚本仍可独立运行：

```bash
cd /path/to/ZHS
source .venv/bin/activate
python main.py
python main.py --fetch
python main.py -c <course_id>
python main.py -c <course_id> -v <video_id>
```

## Linux 部署

下面是一个最短可用的 Linux 部署方案：

- `FastAPI + uvicorn` 作为后端
- `Vite build + Nginx` 作为前端静态资源服务
- `systemd` 托管后端进程

仓库内已附带这些部署文件：

- `docker-compose.yml`
- `docker-compose.prebuilt.yml`
- `web-demo/backend/Dockerfile`
- `web-demo/Dockerfile`
- `web-demo/Dockerfile.prebuilt`
- `web-demo/nginx.conf`
- `deploy/install.sh`
- `deploy/logrotate/zhs`
- `deploy/systemd/zhs-backend.service`
- `deploy/systemd/zhs-backend.env.example`
- `deploy/nginx/zhs.conf`
- `deploy/nginx/zhs.ssl.conf`
- `Makefile`

### 一键安装脚本

如果你使用的是 Debian/Ubuntu 系 Linux，可以直接用仓库内脚本完成原生部署：

```bash
cd /opt/ZHS
sudo DOMAIN=your-domain.example.com DEPLOY_USER=$(whoami) bash deploy/install.sh
```

脚本会自动完成：

- 安装 Python、Node.js、Nginx、rsync
- 同步项目到目标目录
- 创建虚拟环境并安装依赖
- 构建前端
- 生成 `/etc/zhs/zhs-backend.env`
- 安装 `systemd` 服务
- 写入并启用 Nginx 配置
- 安装 `logrotate` 规则

如果你希望用其他路径或端口，可以覆盖这些环境变量：

```bash
sudo INSTALL_DIR=/srv/ZHS \
  DEPLOY_USER=$(whoami) \
  DOMAIN=your-domain.example.com \
  BACKEND_HOST=127.0.0.1 \
  BACKEND_PORT=8000 \
  bash deploy/install.sh
```

### Docker Compose 部署

如果机器已经装好了 Docker 和 Docker Compose，可以直接使用：

```bash
cd /opt/ZHS
mkdir -p logs web-demo/backend/runtime
docker compose up -d --build
```

如果机器拉取 `node` 构建镜像较慢，但前端已经在本地执行过 `npm run build`，可以改用预构建前端镜像路径：

```bash
cd /opt/ZHS/web-demo
npm install
npm run build

cd /opt/ZHS
docker compose -f docker-compose.yml -f docker-compose.prebuilt.yml up -d --build
```

默认暴露：

- 前端：`http://127.0.0.1:8080`
- 后端：仅在 Compose 内部供 Nginx 反代，不直接对外暴露

查看日志：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

### 1. 安装系统依赖

以 Ubuntu 24.04 为例：

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm nginx git
```

### 2. 克隆仓库

```bash
cd /opt
sudo git clone https://github.com/Lazywords2006/ZHS.git
sudo chown -R <deploy-user>:<deploy-user> /opt/ZHS
cd /opt/ZHS
```

### 3. 安装 Python 与前端依赖

```bash
cd /opt/ZHS
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r web-demo/backend/requirements.txt

cd /opt/ZHS/web-demo
npm install
cp .env.example .env.local
```

编辑 `/opt/ZHS/web-demo/.env.local`：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=https://your-domain.example.com
```

然后构建前端：

```bash
cd /opt/ZHS/web-demo
npm run build
```

### 4. 创建后端 systemd 服务

可直接复制仓库里的模板文件 `deploy/systemd/zhs-backend.service` 到系统目录，再按实际部署用户修改 `User`、`Group` 和路径。

创建 `/etc/systemd/system/zhs-backend.service`：

```ini
[Unit]
Description=ZHS FastAPI Backend
After=network.target

[Service]
Type=simple
User=<deploy-user>
Group=<deploy-user>
WorkingDirectory=/opt/ZHS/web-demo/backend
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/ZHS/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zhs-backend.service
sudo systemctl status zhs-backend.service
```

### 5. 配置 Nginx

可直接复制仓库里的模板文件 `deploy/nginx/zhs.conf` 到 `/etc/nginx/sites-available/zhs.conf` 后再修改域名。

创建 `/etc/nginx/sites-available/zhs.conf`：

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    root /opt/ZHS/web-demo/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用站点：

```bash
sudo ln -sf /etc/nginx/sites-available/zhs.conf /etc/nginx/sites-enabled/zhs.conf
sudo nginx -t
sudo systemctl reload nginx
```

如需 HTTPS，建议再接入 `certbot` 或你现有的反向代理。
仓库里也附带了一份可直接改域名和证书路径的模板：`deploy/nginx/zhs.ssl.conf`。

## 运行时数据

以下文件是运行时数据，不应提交到仓库：

- `config.json`
- `cookies.json`
- `logs/`
- `web-demo/.env.local`
- `web-demo/backend/runtime/accounts.json`
- `web-demo/backend/runtime/login_data.json`

其中：

- `accounts.json` 保存账号配置与运行状态
- `login_data.json` 保存扫码登录态、课程缓存与登录错误

后端启动时会自动尝试恢复本地保存的登录态。  
这能减少重复扫码，但是否仍然有效，最终取决于远端会话是否过期。

## 常用命令

```bash
# 查看后端日志
sudo journalctl -u zhs-backend.service -f

# 重启后端
sudo systemctl restart zhs-backend.service

# 重新构建前端
cd /opt/ZHS/web-demo && npm run build

# 检查后端接口
curl http://127.0.0.1:8000/api/accounts
```

如果你更习惯统一命令入口，也可以直接用仓库根目录的 `Makefile`：

```bash
make check-backend
make build-frontend
make compose-up
make compose-logs
```

## 生产环境建议

- 使用独立部署用户，不要直接用 root 跑后端服务
- 保留 `/etc/zhs/zhs-backend.env` 作为后端环境变量入口
- 优先走 HTTPS，至少在公网环境不要长期裸露 HTTP
- 通过 `curl http://127.0.0.1:8000/api/healthz` 和 `curl http://127.0.0.1/healthz` 做存活检查
- 如果使用 Docker，建议接入外部反向代理或云负载均衡，而不是直接把 8080 暴露到公网
- 使用仓库内的 `deploy/logrotate/zhs` 轮转 `logs/`，避免长期运行后日志无限增长

## 开发说明

- 前端默认支持 `mock` 和 `real` 两套 API
- 后端位于 `web-demo/backend/app.py`
- 前端主要入口位于 `web-demo/src/App.vue`
- 根目录 CLI 与 `web-demo` 后端共用 `fucker.py`

## 许可

本仓库保留原项目的 [LICENSE](./LICENSE)。
