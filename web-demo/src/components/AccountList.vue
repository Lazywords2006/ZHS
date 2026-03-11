<template>
  <el-card shadow="never" class="panel account-panel">
    <template #header>
      <div class="panel-header">
        <div>
          <p class="panel-title">账号列表</p>
          <p class="panel-subtitle">集中查看账号状态与当前进度</p>
        </div>
        <div class="header-actions">
          <el-tag round effect="dark" type="info">{{ accounts.length }} 个账号</el-tag>
          <el-button type="primary" @click.stop="$emit('add-account')">新增账号</el-button>
        </div>
      </div>
    </template>

    <el-empty v-if="!accounts.length" description="还没有账号，先新增一个账号" />

    <div v-else class="account-grid">
      <button
        v-for="account in accounts"
        :key="account.id"
        class="account-card"
        :class="{ active: account.id === activeId }"
        @click="$emit('select', account.id)"
      >
        <div class="account-card__top">
          <el-avatar :size="52" :src="account.avatar" />
          <div class="account-card__meta">
            <strong>{{ account.name }}</strong>
            <span>{{ getStatusText(account) }}</span>
          </div>
          <el-tag :type="getStatusType(account)" round>{{ getStatusText(account) }}</el-tag>
        </div>

        <div class="account-card__body">
          <div class="account-card__row">
            <span>当前课程</span>
            <strong>{{ account.currentCourse }}</strong>
          </div>
          <div class="account-card__row">
            <span>任务状态</span>
            <strong>{{ account.lastRunMessage || getStatusText(account) }}</strong>
          </div>
          <el-progress
            :percentage="account.courseProgress"
            :stroke-width="10"
            :show-text="true"
            :color="progressColor"
          />
        </div>
      </button>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  accounts: {
    type: Array,
    required: true,
  },
  activeId: {
    type: String,
    default: '',
  },
})

defineEmits(['select', 'add-account'])

const statusText = {
  online: '在线',
  offline: '离线',
  running: '刷课中',
  verification_required: '需人工验证',
}

const statusType = {
  online: 'success',
  offline: 'info',
  running: 'warning',
  verification_required: 'danger',
}

function getStatusText(account) {
  if (account?.status === 'offline' && account?.hasSavedLogin) {
    return '已保存登录态'
  }
  return statusText[account?.status] || '未知状态'
}

function getStatusType(account) {
  if (account?.status === 'offline' && account?.hasSavedLogin) {
    return 'success'
  }
  return statusType[account?.status] || 'info'
}

const progressColor = [
  { color: '#ef4444', percentage: 20 },
  { color: '#f59e0b', percentage: 55 },
  { color: '#14b8a6', percentage: 80 },
  { color: '#2563eb', percentage: 100 },
]
</script>

<style scoped>
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
