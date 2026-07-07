<template>
  <main class="workbench ops-page">
    <header class="topbar">
      <div>
        <h1>AgentOps 控制台</h1>
        <p>查看任务持久化、节点追踪、Token 成本和批量评测结果。</p>
      </div>
      <div class="topbar-actions">
        <button class="nav-button" :disabled="loading" @click="loadOps">
          <RefreshCw :size="16" />
          <span>刷新</span>
        </button>
        <button class="nav-button" @click="$emit('back')">
          <ArrowLeft :size="16" />
          <span>返回工作台</span>
        </button>
      </div>
    </header>

    <p v-if="message" class="error-banner">{{ message }}</p>

    <section class="ops-summary-grid">
      <article v-for="item in summaryCards" :key="item.label" class="panel ops-stat">
        <component :is="item.icon" :size="18" />
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>

    <div class="ops-grid">
      <section class="panel">
        <div class="panel-title panel-title-row">
          <div>
            <Activity :size="18" />
            <span>任务记录</span>
          </div>
          <small>{{ tasks.length }} 条</small>
        </div>
        <div class="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th>状态</th>
                <th>问题</th>
                <th>Token</th>
                <th>耗时</th>
                <th>用户</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.task_id">
                <td><span :class="['status-chip', statusClass(task.status)]">{{ statusLabel(task.status) }}</span></td>
                <td class="wide-cell">{{ task.question }}</td>
                <td>{{ task.total_tokens }}</td>
                <td>{{ formatDuration(task.duration_ms) }}</td>
                <td>{{ task.tenant_id }} / {{ task.user_id }}</td>
                <td>
                  <button class="secondary-button table-action" @click="loadTask(task.task_id)">
                    <ChevronRight :size="15" />
                    <span>详情</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!tasks.length && !loading" class="empty-text">暂无任务记录。</p>
      </section>

      <section class="panel">
        <div class="panel-title panel-title-row">
          <div>
            <ClipboardCheck :size="18" />
            <span>评测运行</span>
          </div>
          <button class="secondary-button" :disabled="loading" @click="importEval">
            <Database :size="15" />
            <span>导入最新评测</span>
          </button>
        </div>
        <div class="eval-list">
          <article v-for="run in evalRuns" :key="run.eval_run_id" class="eval-item">
            <div>
              <strong>{{ run.passed }}/{{ run.total }} 通过</strong>
              <span :class="['status-chip', run.failed ? 'open' : 'resolved']">
                {{ run.failed ? `${run.failed} 个失败` : '全部通过' }}
              </span>
            </div>
            <small>{{ formatDate(run.created_at) }}</small>
          </article>
          <p v-if="!evalRuns.length && !loading" class="empty-text">暂无评测运行记录。</p>
        </div>
      </section>
    </div>

    <section v-if="selectedTask" class="panel ops-detail">
      <div class="panel-title panel-title-row">
        <div>
          <Timer :size="18" />
          <span>任务详情</span>
        </div>
        <small>{{ selectedTask.task.trace_id }}</small>
      </div>

      <div class="detail-strip">
        <span>模型：{{ selectedTask.task.model_name }}</span>
        <span>Prompt：{{ selectedTask.task.prompt_version }}</span>
        <span>预算：{{ selectedTask.task.token_budget }}</span>
        <span>成本：${{ selectedTask.task.estimated_cost_usd.toFixed(6) }}</span>
      </div>

      <div class="ops-detail-grid">
        <div>
          <h3>节点 Trace</h3>
          <div class="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>节点</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th>输出摘要</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="span in selectedTask.trace" :key="span.span_id">
                  <td>{{ span.name }}</td>
                  <td>{{ span.span_type }}</td>
                  <td>{{ statusLabel(span.status) }}</td>
                  <td>{{ formatDuration(span.duration_ms) }}</td>
                  <td class="wide-cell">{{ span.error || span.output_summary }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3>Token 记录</h3>
          <div class="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>节点</th>
                  <th>输入</th>
                  <th>输出</th>
                  <th>合计</th>
                  <th>成本</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="usage in selectedTask.token_usage" :key="usage.usage_id">
                  <td>{{ usage.node || '-' }}</td>
                  <td>{{ usage.prompt_tokens }}</td>
                  <td>{{ usage.completion_tokens }}</td>
                  <td>{{ usage.total_tokens }}</td>
                  <td>${{ usage.estimated_cost_usd.toFixed(6) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, ArrowLeft, ChevronRight, ClipboardCheck, Coins, Database, RefreshCw, Timer } from '@lucide/vue'
import { getAgentOpsSummary, getAgentTask, importLatestEvalRun, listAgentTasks, listEvalRuns } from '../api/ops'
import type { AgentOpsSummary, AgentTaskDetailResponse, AgentTaskRecord, EvalRunRecord } from '../api/types'

defineEmits<{ back: [] }>()

const loading = ref(false)
const message = ref<string | null>(null)
const summary = ref<AgentOpsSummary | null>(null)
const tasks = ref<AgentTaskRecord[]>([])
const evalRuns = ref<EvalRunRecord[]>([])
const selectedTask = ref<AgentTaskDetailResponse | null>(null)

const summaryCards = computed(() => [
  { label: '任务总数', value: summary.value?.task_count ?? 0, icon: Activity },
  { label: '运行中', value: summary.value?.running_count ?? 0, icon: Timer },
  { label: '失败任务', value: summary.value?.failed_count ?? 0, icon: ClipboardCheck },
  { label: 'Token 合计', value: summary.value?.total_tokens ?? 0, icon: Database },
  { label: '估算成本', value: `$${(summary.value?.estimated_cost_usd ?? 0).toFixed(6)}`, icon: Coins }
])

async function loadOps() {
  loading.value = true
  message.value = null
  try {
    const [summaryResponse, taskResponse, evalResponse] = await Promise.all([
      getAgentOpsSummary(),
      listAgentTasks(30),
      listEvalRuns(10)
    ])
    summary.value = summaryResponse
    tasks.value = taskResponse.tasks
    evalRuns.value = evalResponse.eval_runs
    if (!selectedTask.value && taskResponse.tasks[0]) {
      await loadTask(taskResponse.tasks[0].task_id)
    }
  } catch (err) {
    message.value = err instanceof Error ? err.message : 'AgentOps 数据加载失败。'
  } finally {
    loading.value = false
  }
}

async function loadTask(taskId: string) {
  selectedTask.value = await getAgentTask(taskId)
}

async function importEval() {
  loading.value = true
  message.value = null
  try {
    const run = await importLatestEvalRun()
    evalRuns.value = [run, ...evalRuns.value].slice(0, 10)
    summary.value = await getAgentOpsSummary()
  } catch (err) {
    message.value = err instanceof Error ? err.message : '评测结果导入失败。'
  } finally {
    loading.value = false
  }
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    succeeded: '已成功',
    failed: '已失败',
    cancelled: '已取消',
    open: '待处理',
    resolved: '已解决'
  }
  return labels[status] ?? status
}

function statusClass(status: string): string {
  if (status === 'succeeded') return 'resolved'
  if (status === 'failed' || status === 'cancelled') return 'open'
  return 'monitoring'
}

function formatDuration(value?: number | null): string {
  if (value === null || value === undefined) return '-'
  if (value < 1000) return `${value} ms`
  return `${(value / 1000).toFixed(2)} s`
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

onMounted(loadOps)
</script>
