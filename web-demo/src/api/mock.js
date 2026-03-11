const delay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms))

const accounts = []

const courses = [
  { id: 'course-1', name: '马克思主义基本原理' },
  { id: 'course-2', name: '思想道德与法治' },
  { id: 'course-3', name: '大学英语（下）' },
  { id: 'course-4', name: '高等数学基础' },
  { id: 'course-5', name: '信息素养导论' },
]

let qrState = {
  token: 'init-token',
  expiresIn: 120,
  imageDataUrl: '',
  status: 'pending',
  createdAt: 0,
}
let accountCounter = 1

function createMockAccount(name) {
  const id = `acc-${accountCounter}`
  accountCounter += 1
  return {
    id,
    name,
    avatar: `https://api.dicebear.com/9.x/thumbs/svg?seed=${id}`,
    status: 'offline',
    courseProgress: 0,
    currentCourse: '未开始',
    useWatchLimit: false,
    watchMinutes: 30,
    autoRunDaily: false,
    autoRunDays: 1,
    autoRunUntil: '',
    courseIds: [],
    lastRunMessage: '',
  }
}

function computeAutoRunUntil(days) {
  const safeDays = Math.max(Number(days) || 1, 1)
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + safeDays - 1)
  return date.toISOString().slice(0, 10)
}

function makeQrDataUrl(text) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240">
      <rect width="240" height="240" rx="18" fill="#ffffff"/>
      <rect x="18" y="18" width="204" height="204" rx="12" fill="#0f172a"/>
      <rect x="34" y="34" width="172" height="172" rx="10" fill="#ffffff"/>
      <rect x="46" y="46" width="42" height="42" fill="#0f172a"/>
      <rect x="152" y="46" width="42" height="42" fill="#0f172a"/>
      <rect x="46" y="152" width="42" height="42" fill="#0f172a"/>
      <rect x="112" y="106" width="16" height="16" fill="#0f172a"/>
      <rect x="132" y="106" width="16" height="16" fill="#0f172a"/>
      <rect x="112" y="126" width="16" height="16" fill="#0f172a"/>
      <rect x="132" y="146" width="16" height="16" fill="#0f172a"/>
      <rect x="152" y="126" width="16" height="16" fill="#0f172a"/>
      <rect x="172" y="146" width="16" height="16" fill="#0f172a"/>
      <text x="120" y="224" text-anchor="middle" font-size="11" fill="#94a3b8">${text}</text>
    </svg>
  `
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function resetQr(accountId) {
  const token = `${accountId}-${Math.random().toString(36).slice(2, 8)}`
  qrState = {
    token,
    expiresIn: 120,
    imageDataUrl: makeQrDataUrl(token),
    status: 'pending',
    createdAt: Date.now(),
  }
}

function tickRuns() {
  const now = Date.now()
  for (const account of accounts) {
    if (account.status !== 'running' || !account._runStartedAt || !account._runDuration) {
      continue
    }

    const progress = Math.min(100, Math.floor(((now - account._runStartedAt) / account._runDuration) * 100))
    account.courseProgress = progress
    account.currentCourse = courses.find((item) => account.courseIds.includes(item.id))?.name || '未开始'
    account.lastRunMessage = progress >= 100
      ? '任务完成'
      : `正在刷课，整体进度 ${progress}%`
    if (progress >= 100) {
      account.status = 'online'
      delete account._runStartedAt
      delete account._runDuration
    }
  }
}

export async function fetchAccounts() {
  await delay()
  tickRuns()
  return structuredClone(accounts)
}

export async function createAccount(name) {
  await delay(180)
  const account = createMockAccount(name || `账号 ${accountCounter}`)
  accounts.push(account)
  return structuredClone(account)
}

export async function deleteAccount(accountId) {
  await delay(180)
  const index = accounts.findIndex((item) => item.id === accountId)
  if (index === -1) {
    throw new Error('账号不存在')
  }
  if (accounts[index].status === 'running') {
    throw new Error('请先停止该账号的刷课任务，再删除账号')
  }
  accounts.splice(index, 1)
  return {
    status: 'deleted',
    message: '账号已删除',
  }
}

export async function fetchCourses() {
  await delay()
  return structuredClone(courses)
}

export async function saveAccountConfig(accountId, payload) {
  await delay()
  const target = accounts.find((item) => item.id === accountId)
  if (!target) {
    throw new Error('账号不存在')
  }

  target.courseIds = payload.courseIds
  target.useWatchLimit = Boolean(payload.useWatchLimit)
  target.watchMinutes = payload.watchMinutes
  target.autoRunDaily = payload.autoRunDaily
  target.autoRunDays = payload.autoRunDays
  target.autoRunUntil = payload.autoRunDaily ? computeAutoRunUntil(payload.autoRunDays) : ''
  return structuredClone(target)
}

export async function fetchQrCode(accountId) {
  await delay(180)
  resetQr(accountId)
  return structuredClone(qrState)
}

export async function refreshQrCode(accountId) {
  await delay(180)
  resetQr(accountId)
  return structuredClone(qrState)
}

export async function fetchQrStatus(accountId, token) {
  await delay(120)
  if (!token || token !== qrState.token) {
    return {
      status: 'expired',
      message: '二维码已失效',
    }
  }

  const elapsed = Date.now() - qrState.createdAt
  if (elapsed >= 5000) {
    const target = accounts.find((item) => item.id === accountId)
    if (target) {
      target.status = 'online'
    }
    return {
      status: 'confirmed',
      message: '登录成功',
    }
  }

  if (elapsed >= 2500) {
    return {
      status: 'scanned',
      message: '已扫码，请在手机上确认',
    }
  }

  return {
    status: 'pending',
    message: '等待扫码',
  }
}

export async function startRun(accountId) {
  await delay(180)
  const target = accounts.find((item) => item.id === accountId)
  if (!target) {
    throw new Error('账号不存在')
  }
  if (!target.courseIds.length) {
    throw new Error('请先选择至少一门课程')
  }
  target.status = 'running'
  target.courseProgress = 0
  target.currentCourse = courses.find((item) => target.courseIds.includes(item.id))?.name || '未开始'
  target.lastRunMessage = '任务已启动'
  target._runStartedAt = Date.now()
  target._runDuration = 30000
  return {
    status: 'running',
    message: '刷课任务已启动',
  }
}

export async function stopRun(accountId) {
  await delay(180)
  const target = accounts.find((item) => item.id === accountId)
  if (!target || target.status !== 'running') {
    throw new Error('当前没有运行中的任务')
  }
  target.status = 'online'
  target.lastRunMessage = '已手动停止'
  delete target._runStartedAt
  delete target._runDuration
  return {
    status: 'stopping',
    message: '停止请求已提交',
  }
}
