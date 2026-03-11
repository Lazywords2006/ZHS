# 自动化工具管理界面

这是放在当前仓库里的独立 Vue 3 + Element Plus 前端示例。

- 多账号管理列表
- 扫码登录弹窗
- 课程配置表单
- 实时进度展示

## 启动

```bash
cd /Users/lazywords/Code/fuckZHS-2.6.1/web-demo
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

## 当前实现

- 页面默认使用本地 mock API，文件在 `src/api/mock.js`
- 账号列表支持在线、离线、刷课中三种状态
- 扫码登录弹窗会展示“来自后端”的二维码，并带 120 秒倒计时自动刷新
- 课程列表支持单选或多选
- 每节课观看时长默认 30 分钟
- 支持每日自动执行开关
- 当前课程完成度使用 Element Plus 进度条和仪表盘展示

## 如何切到真实后端

默认走 mock。要切真实后端，新建 `.env.local`：

```bash
cp .env.example .env.local
```

然后改成：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://你的后端地址
```

真实请求入口已经放在 `src/api/real.js`。

仓库现在还附带了一个可以直接运行的 Python 示例后端，目录在 `backend/`。

后端启动：

```bash
cd /Users/lazywords/Code/fuckZHS-2.6.1/web-demo/backend
/opt/homebrew/bin/python3.11 -m pip install -r requirements.txt
/opt/homebrew/bin/python3.11 -m uvicorn app:app --reload --port 8000
```

前端启动：

```bash
cd /Users/lazywords/Code/fuckZHS-2.6.1/web-demo
npm install
npm run dev
```

这个示例后端会：

- 不再预置固定账号，账号由你在页面里自行新增
- 维护账号配置
- 发起并轮询二维码登录
- 使用根目录 `Fucker` 类拉取真实课程列表
- 支持从前端直接发起和停止刷课任务
- 把账号配置和扫码登录数据分开存到 `backend/runtime/accounts.json` 与 `backend/runtime/login_data.json`

注意：

- 当前 `web-demo/` 只是独立前端示例
- 不会修改或调用仓库根目录下原有 Python 运行逻辑

示例后端对齐这些接口：

- `GET /api/accounts`
- `POST /api/accounts`
- `DELETE /api/accounts/:id`
- `GET /api/courses?accountId=...`
- `POST /api/accounts/:id/config`
- `POST /api/accounts/:id/login/qr`
- `POST /api/accounts/:id/login/qr/refresh`
- `GET /api/accounts/:id/login/qr/status?token=...`
- `POST /api/accounts/:id/run/start`
- `POST /api/accounts/:id/run/stop`

二维码接口返回：

```json
{
  "token": "abc123",
  "expiresIn": 120,
  "imageDataUrl": "data:image/png;base64,...",
  "status": "pending"
}
```
