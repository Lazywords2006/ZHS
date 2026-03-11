# web-demo 示例后端

这个目录提供了一个最小可用的 Python 示例后端，用来把 `web-demo/` 从 mock API 切到真实接口。

它做的事情只有三类：

- 由页面动态新增账号，不再预置固定账号
- 维护账号配置
- 发起并轮询智慧树二维码登录
- 用根目录的 `Fucker` 类拉真实课程列表
- 在后台线程里启动和停止刷课任务

## 运行

请使用 Python 3.11+。根目录代码使用了 `match/case`，3.9 不能跑。

```bash
cd /Users/lazywords/Code/fuckZHS-2.6.1/web-demo/backend
/opt/homebrew/bin/python3.11 -m pip install -r requirements.txt
/opt/homebrew/bin/python3.11 -m uvicorn app:app --reload --port 8000
```

运行时会自动创建：

- `runtime/accounts.json`：账号基础配置、运行状态
- `runtime/login_data.json`：扫码登录保存的 cookies、课程缓存、登录错误信息

## 接口

- `GET /api/accounts`
- `POST /api/accounts`
- `DELETE /api/accounts/:id`
- `GET /api/courses?accountId=acc-1`
- `POST /api/accounts/:id/config`
- `POST /api/accounts/:id/login/qr`
- `POST /api/accounts/:id/login/qr/refresh`
- `GET /api/accounts/:id/login/qr/status?token=...`
- `POST /api/accounts/:id/run/start`
- `POST /api/accounts/:id/run/stop`

二维码状态使用：

- `pending`
- `scanned`
- `confirmed`
- `expired`
- `cancelled`
- `error`

## 与前端联调

在 `web-demo/` 里创建 `.env.local`：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

然后启动前端：

```bash
cd /Users/lazywords/Code/fuckZHS-2.6.1/web-demo
npm install
npm run dev
```

## 说明

- 这是示例接入，不是生产级多租户服务
- 课程列表按当前账号实时拉取；如果远端失败，会回退到本地缓存
- 当前前端已经可以从界面直接启动和停止刷课任务
- 停止是协作式的：当前正在执行的课程会先跑完，再在下一门课之前停下
