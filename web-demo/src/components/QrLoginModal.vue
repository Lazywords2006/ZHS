<template>
  <el-dialog
    :model-value="visible"
    width="420px"
    destroy-on-close
    align-center
    class="qr-dialog"
    @close="$emit('close')"
  >
    <template #header>
      <div class="dialog-head">
        <div>
          <h3>扫码登录</h3>
          <p>{{ accountName || '未选择账号' }}</p>
        </div>
        <el-tag type="warning" round>剩余 {{ countdown }} 秒</el-tag>
      </div>
    </template>

    <div class="qr-box">
      <img v-if="qrImageUrl" :src="qrImageUrl" alt="登录二维码" class="qr-image" />
      <el-skeleton v-else animated :rows="6" />
    </div>

    <el-alert
      :closable="false"
      type="info"
      show-icon
      :title="statusText"
      description="二维码来自后端接口；登录完成后页面会自动刷新账号状态。"
    />

    <template #footer>
      <div class="dialog-actions">
        <el-button @click="$emit('close')">关闭</el-button>
        <el-button type="primary" @click="$emit('refresh')">立即刷新二维码</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  qrImageUrl: {
    type: String,
    default: '',
  },
  countdown: {
    type: Number,
    default: 0,
  },
  accountName: {
    type: String,
    default: '',
  },
  statusText: {
    type: String,
    default: '等待扫码',
  },
})

defineEmits(['close', 'refresh'])
</script>
