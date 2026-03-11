<template>
  <el-card shadow="never" class="panel">
    <template #header>
      <div class="panel-header">
        <div>
          <p class="panel-title">课程配置</p>
          <p class="panel-subtitle">为当前账号设置课程、时长与自动执行策略</p>
        </div>
        <div class="panel-actions">
          <el-button @click="$emit('refresh-courses')" :disabled="!account">
            刷新课程
          </el-button>
          <el-button
            type="danger"
            plain
            @click="$emit('delete-account')"
            :disabled="!account"
          >
            删除账号
          </el-button>
          <el-button plain @click="$emit('open-official-page')" :disabled="!account">
            打开官方页面
          </el-button>
          <el-button type="primary" @click="$emit('open-login')" :disabled="!account">
            扫码登录
          </el-button>
        </div>
      </div>
    </template>

    <el-empty v-if="!account" description="请选择一个账号后再配置" />

      <el-form
      v-else
      label-position="top"
      class="config-form"
      @submit.prevent
    >
      <div class="config-hero">
        <div class="config-hero__left">
          <el-avatar :src="account.avatar" :size="60" />
          <div>
            <h3>{{ account.name }}</h3>
            <p>{{ account.currentCourse }}</p>
          </div>
        </div>
        <el-progress
          type="dashboard"
          :percentage="account.courseProgress"
          :width="118"
          :stroke-width="12"
          color="#2563eb"
        >
          <template #default="{ percentage }">
            <div class="dashboard-slot">
              <strong>{{ percentage }}%</strong>
              <span>完成度</span>
            </div>
          </template>
        </el-progress>
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="14">
          <el-form-item label="课程列表">
            <el-select
              v-model="courseModel"
              :multiple="multiple"
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择课程"
              class="full-width"
            >
              <el-option
                v-for="course in courses"
                :key="course.id"
                :label="course.name"
                :value="course.id"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :md="12" :lg="5">
          <el-form-item label="每节课观看时长（分钟）">
            <div class="limit-control">
              <div class="switch-wrap">
                <el-switch
                  v-model="localConfig.useWatchLimit"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
                <span class="switch-help">
                  {{ localConfig.useWatchLimit ? '达到设定分钟数后结束当前课程' : '默认一直观看' }}
                </span>
              </div>
              <el-input-number
                v-model="localConfig.watchMinutes"
                :min="1"
                :max="180"
                :step="5"
                :disabled="!localConfig.useWatchLimit"
                controls-position="right"
                class="full-width"
              />
            </div>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :md="12" :lg="5">
          <el-form-item label="每日自动执行">
            <div class="limit-control">
              <div class="switch-wrap">
                <el-switch v-model="localConfig.autoRunDaily" inline-prompt active-text="开" inactive-text="关" />
                <span class="switch-help">{{ localConfig.autoRunDaily ? '已启用定时执行' : '仅手动触发' }}</span>
              </div>
              <div class="auto-run-range">
                <el-input-number
                  v-model="localConfig.autoRunDays"
                  :min="1"
                  :max="365"
                  :disabled="!localConfig.autoRunDaily"
                  controls-position="right"
                  class="auto-run-days"
                />
                <el-tag round effect="plain" :type="localConfig.autoRunDaily ? 'success' : 'info'">
                  截止 {{ autoRunUntilPreview }}
                </el-tag>
              </div>
              <span class="switch-help">
                {{ localConfig.autoRunDaily ? '按自然日计算，1 天表示今天截止' : '开启后可按天数自动换算截止日期' }}
              </span>
            </div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="选择模式">
        <el-radio-group v-model="selectionMode">
          <el-radio-button label="single">单选</el-radio-button>
          <el-radio-button label="multiple">多选</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-alert
        v-if="account.status === 'verification_required'"
        :closable="false"
        type="warning"
        show-icon
        class="run-alert"
        title="当前账号需要人工验证"
        :description="account.lastRunMessage || '请先在浏览器或官方客户端完成验证，再回来重试。'"
      />

      <div v-if="account.status === 'verification_required'" class="verification-actions">
        <el-button plain @click="$emit('open-official-page')">
          打开官方页面
        </el-button>
        <el-button type="primary" @click="$emit('open-login')">
          验证后重新扫码
        </el-button>
      </div>

      <el-alert
        :closable="false"
        type="info"
        show-icon
        class="run-alert"
        :title="runStatusTitle"
        :description="account.lastRunMessage || '登录后即可从这里直接发起刷课任务。'"
      />

      <div class="form-actions">
        <el-button @click="resetConfig">恢复当前账号配置</el-button>
        <el-button type="primary" @click="submit">保存配置</el-button>
        <el-button
          type="success"
          @click="startRun"
          :disabled="!canStartRun"
        >
          开始刷课
        </el-button>
        <el-button
          type="danger"
          plain
          @click="$emit('stop-run')"
          :disabled="account.status !== 'running'"
        >
          停止刷课
        </el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  account: {
    type: Object,
    default: null,
  },
  courses: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits([
  'save',
  'open-login',
  'refresh-courses',
  'delete-account',
  'start-run',
  'stop-run',
  'open-official-page',
])

const localConfig = reactive({
  courseIds: [],
  useWatchLimit: false,
  watchMinutes: 30,
  autoRunDaily: false,
  autoRunDays: 1,
})

const selectionMode = ref('multiple')

const courseModel = computed({
  get: () => (selectionMode.value === 'multiple' ? localConfig.courseIds : localConfig.courseIds[0] ?? ''),
  set: (value) => {
    if (Array.isArray(value)) {
      localConfig.courseIds = value
      return
    }
    localConfig.courseIds = value ? [value] : []
  },
})

const multiple = computed(() => selectionMode.value === 'multiple')
const canStartRun = computed(() => {
  if (!props.account) {
    return false
  }
  if (props.account.status === 'running') {
    return false
  }
  if (props.account.status === 'offline' && !props.account.hasSavedLogin) {
    return false
  }
  if (props.account.status === 'verification_required') {
    return false
  }
  return localConfig.courseIds.length > 0
})
const runStatusTitle = computed(() => {
  if (props.account?.status === 'offline' && props.account?.hasSavedLogin) {
    return '已保存登录态'
  }
  const textMap = {
    offline: '账号离线',
    online: '账号在线',
    running: '任务执行中',
    verification_required: '等待人工验证',
  }
  return textMap[props.account?.status] || '等待操作'
})
const autoRunUntilPreview = computed(() => {
  const savedMatchesCurrent =
    Number(props.account?.autoRunDays ?? 1) === Number(localConfig.autoRunDays)
    && Boolean(props.account?.autoRunDaily) === Boolean(localConfig.autoRunDaily)

  if (savedMatchesCurrent && props.account?.autoRunUntil) {
    return props.account.autoRunUntil
  }

  return formatAutoRunUntil(localConfig.autoRunDays)
})

function formatAutoRunUntil(days) {
  const safeDays = Math.max(Number(days) || 1, 1)
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + safeDays - 1)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getPayload() {
  return {
    courseIds: [...localConfig.courseIds],
    useWatchLimit: localConfig.useWatchLimit,
    watchMinutes: localConfig.watchMinutes,
    autoRunDaily: localConfig.autoRunDaily,
    autoRunDays: localConfig.autoRunDays,
  }
}

function syncFromAccount(account) {
  localConfig.courseIds = [...(account?.courseIds ?? [])]
  localConfig.useWatchLimit = account?.useWatchLimit ?? false
  localConfig.watchMinutes = account?.watchMinutes ?? 30
  localConfig.autoRunDaily = account?.autoRunDaily ?? false
  localConfig.autoRunDays = account?.autoRunDays ?? 1
  selectionMode.value = localConfig.courseIds.length > 1 ? 'multiple' : 'single'
}

function resetConfig() {
  syncFromAccount(props.account)
}

function submit() {
  emit('save', getPayload())
}

function startRun() {
  emit('start-run', getPayload())
}

watch(
  () => props.account,
  (account) => {
    syncFromAccount(account)
  },
  { immediate: true },
)

watch(
  () => selectionMode.value,
  (value) => {
    if (value === 'single' && localConfig.courseIds.length > 1) {
      localConfig.courseIds = localConfig.courseIds.slice(0, 1)
    }
  },
)
</script>

<style scoped>
.panel-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.run-alert {
  margin-bottom: 18px;
}

.verification-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.limit-control {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.switch-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.switch-help {
  color: #64748b;
  font-size: 13px;
  line-height: 1.4;
}

.auto-run-range {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.auto-run-days {
  flex: 1 1 120px;
}
</style>
