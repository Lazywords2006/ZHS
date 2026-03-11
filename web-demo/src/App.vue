<template>
  <div class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Vue 3 + Element Plus</p>
        <h1>自动化工具管理界面</h1>
        <p class="hero-copy">
          演示多账号管理、扫码登录、课程配置和实时进度展示的前端结构。
        </p>
      </div>
      <div class="hero-stats">
        <el-statistic title="在线账号" :value="onlineCount" />
        <el-statistic title="刷课中" :value="runningCount" />
      </div>
    </section>

    <main class="layout">
      <AccountList
        :accounts="accounts"
        :active-id="activeAccountId"
        @add-account="handleAddAccount"
        @select="handleSelectAccount"
      />

      <CourseConfigPanel
        :account="activeAccount"
        :courses="courses"
        @save="handleSaveConfig"
        @refresh-courses="handleRefreshCourses"
        @delete-account="handleDeleteAccount"
        @start-run="handleStartRun"
        @stop-run="handleStopRun"
        @open-login="openQrDialog"
        @open-official-page="openOfficialPage"
      />
    </main>

    <QrLoginModal
      :visible="qrVisible"
      :account-name="activeAccount?.name"
      :qr-image-url="qrState.imageDataUrl"
      :countdown="countdown"
      :status-text="qrStatusText"
      @close="closeQrDialog"
      @refresh="refreshQr"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import AccountList from './components/AccountList.vue'
import CourseConfigPanel from './components/CourseConfigPanel.vue'
import QrLoginModal from './components/QrLoginModal.vue'
import {
  fetchAccounts,
  fetchCourses,
  createAccount,
  deleteAccount,
  fetchQrCode,
  fetchQrStatus,
  refreshQrCode,
  saveAccountConfig,
  startRun,
  stopRun,
} from './api'

const accounts = ref([])
const courses = ref([])
const activeAccountId = ref('')
const qrVisible = ref(false)
const countdown = ref(0)
const OFFICIAL_LOGIN_URL = 'https://passport.zhihuishu.com/login?service=https://onlineservice-api.zhihuishu.com/login/gologin'
const qrState = reactive({
  token: '',
  expiresIn: 0,
  imageDataUrl: '',
  status: 'pending',
})

let countdownTimerId = null
let qrStatusTimerId = null
let accountPollTimerId = null

const activeAccount = computed(() => accounts.value.find((item) => item.id === activeAccountId.value) ?? null)
const onlineCount = computed(() => accounts.value.filter((item) => item.status === 'online').length)
const runningCount = computed(() => accounts.value.filter((item) => item.status === 'running').length)
const qrStatusText = computed(() => {
  const textMap = {
    pending: '等待扫码',
    scanned: '已扫码，请在手机上确认',
    confirmed: '登录成功，正在刷新账号状态',
    expired: '二维码已过期',
    cancelled: '登录已取消',
    error: '登录失败，请重试',
  }
  return textMap[qrState.status] || '等待扫码'
})

async function loadInitialData() {
  await refreshAccountData({ reloadCourses: false })
}

async function loadCourses(accountId = activeAccountId.value) {
  if (!accountId) {
    courses.value = []
    return
  }
  courses.value = await fetchCourses(accountId)
  await refreshAccountData({ reloadCourses: false })
}

async function refreshAccountData(options = {}) {
  const { reloadCourses = false } = options
  const currentId = activeAccountId.value
  accounts.value = await fetchAccounts()
  activeAccountId.value = accounts.value.some((item) => item.id === currentId)
    ? currentId
    : accounts.value[0]?.id ?? ''
  if (reloadCourses && activeAccountId.value) {
    await loadCourses(activeAccountId.value)
  }
}

async function handleSelectAccount(accountId) {
  activeAccountId.value = accountId
}

async function handleAddAccount() {
  try {
    const { value } = await ElMessageBox.prompt('输入账号名称', '新增账号', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：我的主账号',
    })
    const created = await createAccount(value)
    await refreshAccountData({ reloadCourses: false })
    activeAccountId.value = created.id
    courses.value = []
    ElMessage.success('账号已创建')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error.message || '账号创建失败')
  }
}

async function handleDeleteAccount() {
  if (!activeAccount.value) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `删除账号“${activeAccount.value.name}”会同时清理本地保存的扫码登录数据。`,
      '删除账号',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    const deletingId = activeAccount.value.id
    const result = await deleteAccount(deletingId)
    if (activeAccountId.value === deletingId) {
      activeAccountId.value = ''
      courses.value = []
    }
    await refreshAccountData({ reloadCourses: false })
    ElMessage.success(result.message || '账号已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error.message || '账号删除失败')
  }
}

async function handleSaveConfig(payload) {
  if (!activeAccount.value) {
    return
  }
  try {
    const updated = await saveAccountConfig(activeAccount.value.id, payload)
    const index = accounts.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) {
      accounts.value[index] = updated
    }
    ElMessage.success('课程配置已保存')
  } catch (error) {
    ElMessage.error(error.message || '课程配置保存失败')
  }
}

async function handleRefreshCourses() {
  if (!activeAccount.value) {
    return
  }
  try {
    await loadCourses(activeAccount.value.id)
    ElMessage.success('课程列表已刷新')
  } catch (error) {
    ElMessage.error(error.message || '课程列表刷新失败')
  }
}

async function handleStartRun(payload) {
  if (!activeAccount.value) {
    return
  }
  try {
    const updated = await saveAccountConfig(activeAccount.value.id, payload)
    const index = accounts.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) {
      accounts.value[index] = updated
    }
    const result = await startRun(activeAccount.value.id)
    ElMessage.success(result.message || '刷课任务已启动')
    await refreshAccountData({ reloadCourses: false })
  } catch (error) {
    ElMessage.error(error.message || '刷课任务启动失败')
  }
}

async function handleStopRun() {
  if (!activeAccount.value) {
    return
  }
  try {
    const result = await stopRun(activeAccount.value.id)
    ElMessage.success(result.message || '停止请求已提交')
    await refreshAccountData({ reloadCourses: false })
  } catch (error) {
    ElMessage.error(error.message || '停止请求提交失败')
  }
}

function openOfficialPage() {
  const newWindow = window.open(OFFICIAL_LOGIN_URL, '_blank', 'noopener,noreferrer')
  if (!newWindow) {
    ElMessage.error('官方页面打开失败，请检查浏览器弹窗拦截设置')
    return
  }
  ElMessage.info('官方页面已打开。完成人工验证后，请回到此页面重新扫码登录。')
}

function clearCountdownTimer() {
  if (countdownTimerId) {
    window.clearInterval(countdownTimerId)
    countdownTimerId = null
  }
}

function clearQrStatusTimer() {
  if (qrStatusTimerId) {
    window.clearInterval(qrStatusTimerId)
    qrStatusTimerId = null
  }
}

function clearAccountPollTimer() {
  if (accountPollTimerId) {
    window.clearInterval(accountPollTimerId)
    accountPollTimerId = null
  }
}

function startCountdown() {
  clearCountdownTimer()
  countdown.value = qrState.expiresIn
  countdownTimerId = window.setInterval(async () => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      await refreshQr()
    }
  }, 1000)
}

function startQrStatusPolling(accountId, token) {
  clearQrStatusTimer()
  qrStatusTimerId = window.setInterval(async () => {
    if (!qrVisible.value || !token) {
      return
    }
    try {
      const status = await fetchQrStatus(accountId, token)
      qrState.status = status.status
      if (status.status === 'confirmed') {
        ElMessage.success('扫码登录成功')
        await refreshAccountData({ reloadCourses: true })
        closeQrDialog()
      } else if (status.status === 'error') {
        ElMessage.error(status.message || '扫码登录失败')
        clearQrStatusTimer()
      }
    } catch (error) {
      ElMessage.error(error.message || '二维码状态拉取失败')
      clearQrStatusTimer()
    }
  }, 2000)
}

function startAccountPolling() {
  if (accountPollTimerId) {
    return
  }
  accountPollTimerId = window.setInterval(async () => {
    try {
      await refreshAccountData({ reloadCourses: false })
    } catch (error) {
      ElMessage.error(error.message || '账号状态刷新失败')
      clearAccountPollTimer()
    }
  }, 4000)
}

async function loadQrData(factory) {
  if (!activeAccount.value) {
    return
  }
  const data = await factory(activeAccount.value.id)
  qrState.token = data.token
  qrState.expiresIn = data.expiresIn
  qrState.imageDataUrl = data.imageDataUrl
  qrState.status = data.status || 'pending'
  startCountdown()
  startQrStatusPolling(activeAccount.value.id, data.token)
}

async function openQrDialog() {
  qrVisible.value = true
  await loadQrData(fetchQrCode)
}

async function refreshQr() {
  await loadQrData(refreshQrCode)
}

function closeQrDialog() {
  qrVisible.value = false
  clearCountdownTimer()
  clearQrStatusTimer()
  qrState.token = ''
  qrState.status = 'pending'
}

onMounted(() => {
  loadInitialData()
})

watch(
  () => activeAccountId.value,
  (accountId) => {
    if (accountId) {
      loadCourses(accountId)
    } else {
      courses.value = []
    }
  },
)

watch(
  () => runningCount.value,
  (count) => {
    if (count > 0) {
      startAccountPolling()
    } else {
      clearAccountPollTimer()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  clearCountdownTimer()
  clearQrStatusTimer()
  clearAccountPollTimer()
})
</script>

<style scoped>
.page-shell {
  min-height: 100vh;
  padding: 32px 20px 48px;
}

.hero {
  width: min(1240px, 100%);
  margin: 0 auto 20px;
  padding: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-radius: 28px;
  background: linear-gradient(135deg, #ffffff, #ecf6ff);
  box-shadow: 0 18px 60px rgba(37, 99, 235, 0.12);
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero h1 {
  margin: 0;
  font-size: clamp(32px, 4vw, 46px);
  line-height: 1;
}

.hero-copy {
  max-width: 36rem;
  margin: 12px 0 0;
  color: #526277;
  font-size: 16px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px;
}

.layout {
  width: min(1240px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(320px, 0.95fr) minmax(420px, 1.25fr);
  gap: 20px;
}

:deep(.panel) {
  border: 0;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(12px);
  box-shadow: 0 14px 48px rgba(15, 23, 42, 0.08);
}

:deep(.panel .el-card__header) {
  padding: 22px 24px 0;
  border-bottom: 0;
}

:deep(.panel .el-card__body) {
  padding: 22px 24px 24px;
}

:deep(.panel-header) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

:deep(.panel-title) {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

:deep(.panel-subtitle) {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
}

:deep(.account-grid) {
  display: grid;
  gap: 14px;
}

:deep(.account-card) {
  width: 100%;
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 22px;
  background: linear-gradient(180deg, #fdfefe, #f6f9fc);
  text-align: left;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

:deep(.account-card:hover),
:deep(.account-card.active) {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.44);
  box-shadow: 0 18px 36px rgba(37, 99, 235, 0.1);
}

:deep(.account-card__top) {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
}

:deep(.account-card__meta) {
  display: grid;
  gap: 3px;
}

:deep(.account-card__meta strong) {
  font-size: 16px;
}

:deep(.account-card__meta span) {
  color: #64748b;
  font-size: 13px;
}

:deep(.account-card__body) {
  margin-top: 14px;
}

:deep(.account-card__row) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  color: #64748b;
  font-size: 13px;
}

:deep(.account-card__row strong) {
  color: #132238;
}

:deep(.config-form) {
  display: grid;
  gap: 8px;
}

:deep(.config-hero) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 10px;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(135deg, #eff6ff, #f8fafc);
}

:deep(.config-hero__left) {
  display: flex;
  align-items: center;
  gap: 14px;
}

:deep(.config-hero__left h3) {
  margin: 0;
  font-size: 22px;
}

:deep(.config-hero__left p) {
  margin: 6px 0 0;
  color: #64748b;
}

:deep(.dashboard-slot) {
  display: grid;
  place-items: center;
}

:deep(.dashboard-slot strong) {
  font-size: 24px;
}

:deep(.dashboard-slot span) {
  color: #64748b;
  font-size: 12px;
}

:deep(.full-width) {
  width: 100%;
}

:deep(.switch-wrap) {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 40px;
  justify-content: center;
}

:deep(.switch-help) {
  color: #64748b;
  font-size: 13px;
}

:deep(.form-actions) {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

:deep(.dialog-head) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

:deep(.dialog-head h3) {
  margin: 0;
  font-size: 22px;
}

:deep(.dialog-head p) {
  margin: 6px 0 0;
  color: #64748b;
}

:deep(.qr-box) {
  display: grid;
  place-items: center;
  margin-bottom: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, #f8fbff, #eff3f8);
  padding: 24px;
}

:deep(.qr-image) {
  width: 240px;
  max-width: 100%;
  display: block;
}

:deep(.dialog-actions) {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 960px) {
  .hero,
  .layout {
    width: min(100%, 1180px);
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-stats {
    width: 100%;
  }

  .layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-shell {
    padding: 18px 14px 30px;
  }

  .hero {
    padding: 22px;
    border-radius: 24px;
  }

  :deep(.config-hero) {
    flex-direction: column;
    align-items: flex-start;
  }

  :deep(.form-actions) {
    flex-direction: column;
  }

  :deep(.form-actions .el-button) {
    margin-left: 0;
  }
}
</style>
