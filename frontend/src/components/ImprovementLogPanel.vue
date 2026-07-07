<template>
  <section class="panel improvement-panel">
    <div class="panel-title panel-title-row">
      <div>
        <ClipboardList :size="18" />
        <span>改进日志</span>
      </div>
      <button class="icon-button" title="刷新日志" :disabled="loading" @click="loadLogs">
        <RefreshCw :size="15" />
      </button>
    </div>

    <div class="improvement-form">
      <label>
        <span>问题记录</span>
        <textarea v-model="issue" placeholder="例如：数据质量类问题被误判为描述统计" />
      </label>
      <label>
        <span>解决措施</span>
        <textarea v-model="resolution" placeholder="例如：新增 data_quality 意图、执行真实质量扫描并加入回归测试" />
      </label>
      <div class="form-row">
        <label>
          <span>状态</span>
          <select v-model="statusValue">
            <option value="resolved">已解决</option>
            <option value="monitoring">观察中</option>
            <option value="open">待处理</option>
          </select>
        </label>
        <label>
          <span>关联分析问题</span>
          <input v-model="relatedQuestionValue" placeholder="可关联最近一次分析问题" />
        </label>
      </div>
      <button class="secondary-button" :disabled="saving || !canSubmit" @click="submit">
        <Plus :size="16" />
        <span>{{ saving ? '保存中' : '记录改进' }}</span>
      </button>
      <p v-if="message" class="form-message">{{ message }}</p>
    </div>

    <div class="log-list">
      <article v-for="log in logs" :key="log.log_id" class="log-item">
        <div class="log-head">
          <strong>{{ log.issue }}</strong>
          <span :class="['status-chip', log.status]">{{ statusLabel(log.status) }}</span>
        </div>
        <p>{{ log.resolution }}</p>
        <small>
          {{ formatTime(log.created_at) }}
          <template v-if="log.related_question">｜{{ log.related_question }}</template>
        </small>
      </article>
      <p v-if="!logs.length && !loading" class="empty-text">暂无改进记录。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ClipboardList, Plus, RefreshCw } from '@lucide/vue'
import { createImprovementLog, listImprovementLogs } from '../api/improvements'
import type { ImprovementLogEntry, ImprovementStatus } from '../api/types'

const props = defineProps<{
  datasetId?: string | null
  lastQuestion?: string | null
}>()

const logs = ref<ImprovementLogEntry[]>([])
const issue = ref('')
const resolution = ref('')
const statusValue = ref<ImprovementStatus>('resolved')
const relatedQuestionValue = ref('')
const loading = ref(false)
const saving = ref(false)
const message = ref<string | null>(null)

const canSubmit = computed(() => issue.value.trim().length >= 2 && resolution.value.trim().length >= 2)

watch(
  () => props.lastQuestion,
  (question) => {
    if (question && !relatedQuestionValue.value.trim()) {
      relatedQuestionValue.value = question
    }
  }
)

async function loadLogs() {
  loading.value = true
  message.value = null
  try {
    const response = await listImprovementLogs(20)
    logs.value = response.logs
  } catch (err) {
    message.value = err instanceof Error ? err.message : '日志加载失败。'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  saving.value = true
  message.value = null
  try {
    const created = await createImprovementLog({
      issue: issue.value.trim(),
      resolution: resolution.value.trim(),
      status: statusValue.value,
      dataset_id: props.datasetId || null,
      related_question: relatedQuestionValue.value.trim() || null
    })
    logs.value = [created, ...logs.value].slice(0, 20)
    issue.value = ''
    resolution.value = ''
    message.value = '改进日志已保存。'
  } catch (err) {
    message.value = err instanceof Error ? err.message : '日志保存失败。'
  } finally {
    saving.value = false
  }
}

function statusLabel(status: ImprovementStatus): string {
  const labels: Record<ImprovementStatus, string> = {
    resolved: '已解决',
    monitoring: '观察中',
    open: '待处理'
  }
  return labels[status]
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

onMounted(loadLogs)
</script>
