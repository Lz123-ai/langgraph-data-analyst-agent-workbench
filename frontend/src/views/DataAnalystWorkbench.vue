<template>
  <main class="workbench">
    <header class="topbar platform-topbar">
      <div>
        <h1>LangGraph 数据分析 Agent 工作台</h1>
        <p>上传数据集，输入分析问题，实时查看 Agent 的可追溯执行流程。</p>
      </div>
      <div v-if="profile" class="topbar-metrics">
        <span>{{ profile.row_count }} 行</span>
        <span>{{ profile.column_count }} 列</span>
        <span>{{ profile.numeric_columns.length }} 个数值字段</span>
      </div>
      <div class="topbar-actions">
        <button v-if="running" class="nav-button" @click="handleCancel">
          <span>取消任务</span>
        </button>
        <button class="nav-button" @click="emit('openOps')">
          <Gauge :size="16" />
          <span>AgentOps</span>
        </button>
        <button class="nav-button" @click="emit('openLog', { datasetId: dataset?.dataset_id, lastQuestion })">
          <ClipboardList :size="16" />
          <span>日志</span>
        </button>
        <div class="status-badge" :class="{ running }">
          <Activity :size="16" />
          <span>{{ running ? 'Agent 执行中' : '就绪' }}</span>
        </div>
      </div>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <div class="platform-layout">
      <aside class="asset-column">
        <DatasetUploader :uploading="uploading" @upload="handleUpload" />
        <DataAssetPanel :dataset="dataset" :profile="profile" />
        <DatasetPreview :dataset="dataset" :profile="profile" :rows="previewRows" />
      </aside>

      <section class="analysis-column">
        <QuestionPanel :disabled="!dataset" :running="running" @run="handleRun" />
        <section v-if="subQuestions.length" class="panel subquestion-panel">
          <div class="panel-title">
            <ListChecks :size="18" />
            <span>子问题计划</span>
          </div>
          <ol>
            <li v-for="(item, index) in subQuestions" :key="`${index}-${item}`">
              <strong>问题 {{ index + 1 }}</strong>
              <span>{{ item }}</span>
            </li>
          </ol>
        </section>
        <AgentTimeline :events="events" :running="running" />
        <AnalysisOutputWorkspace
          :charts="charts"
          :result="executionResult"
          :markdown="reportMarkdown"
          :sql-queries="sqlQueries"
          :generated-code="generatedCode"
        />
      </section>

      <ContextInspector
        :dataset="dataset"
        :running="running"
        :events="events"
        :charts="charts"
        :result="executionResult"
        :execution-path="executionPath"
        :sql-queries="sqlQueries"
        :generated-code="generatedCode"
        :sub-questions="subQuestions"
        :report-ready="Boolean(reportMarkdown)"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { Activity, ClipboardList, Gauge, ListChecks } from '@lucide/vue'
import { cancelAnalysisTask, createAnalysisTask, subscribeToTask } from '../api/analysis'
import { uploadDataset } from '../api/datasets'
import type { ChartArtifact, DatasetMetadata, DatasetProfile, ExecutionResult, TaskEvent } from '../api/types'
import AgentTimeline from '../components/AgentTimeline.vue'
import AnalysisOutputWorkspace from '../components/AnalysisOutputWorkspace.vue'
import ContextInspector from '../components/ContextInspector.vue'
import DataAssetPanel from '../components/DataAssetPanel.vue'
import DatasetPreview from '../components/DatasetPreview.vue'
import DatasetUploader from '../components/DatasetUploader.vue'
import QuestionPanel from '../components/QuestionPanel.vue'

const emit = defineEmits<{
  openLog: [context: { datasetId?: string | null; lastQuestion?: string | null }]
  openOps: []
}>()

const uploading = ref(false)
const running = ref(false)
const error = ref<string | null>(null)
const dataset = ref<DatasetMetadata | null>(null)
const profile = ref<DatasetProfile | null>(null)
const previewRows = ref<Array<Record<string, unknown>>>([])
const events = ref<TaskEvent[]>([])
const charts = ref<ChartArtifact[]>([])
const executionResult = ref<ExecutionResult | null>(null)
const reportMarkdown = ref<string | null>(null)
const lastQuestion = ref<string | null>(null)
const executionPath = ref<string | null>(null)
const sqlQueries = ref<string[]>([])
const generatedCode = ref<string[]>([])
const subQuestions = ref<string[]>([])
const currentTaskId = ref<string | null>(null)
let source: EventSource | null = null

async function handleUpload(file: File) {
  uploading.value = true
  error.value = null
  try {
    const response = await uploadDataset(file)
    dataset.value = response.dataset
    profile.value = response.profile
    previewRows.value = response.preview
    events.value = []
    charts.value = []
    executionResult.value = null
    reportMarkdown.value = null
    executionPath.value = null
    sqlQueries.value = []
    generatedCode.value = []
    subQuestions.value = []
  } catch (err) {
    error.value = err instanceof Error ? err.message : '上传失败。'
  } finally {
    uploading.value = false
  }
}

async function handleRun(question: string) {
  if (!dataset.value) return
  source?.close()
  running.value = true
  error.value = null
  lastQuestion.value = question
  events.value = []
  charts.value = []
  executionResult.value = null
  reportMarkdown.value = null
  executionPath.value = null
  sqlQueries.value = []
  generatedCode.value = []
  subQuestions.value = []
  try {
    const task = await createAnalysisTask(dataset.value.dataset_id, question)
    currentTaskId.value = task.task_id
    source = subscribeToTask(task.task_id, handleTaskEvent, (message) => {
      if (running.value) error.value = message
    })
  } catch (err) {
    running.value = false
    error.value = err instanceof Error ? err.message : '分析任务启动失败。'
  }
}

function handleTaskEvent(event: TaskEvent) {
  if (event.event_type !== 'heartbeat') {
    events.value.push(event)
  }
  const payload = event.payload
  if (isRecord(payload.profile)) profile.value = payload.profile as unknown as DatasetProfile
  if (Array.isArray(payload.charts)) charts.value = payload.charts as ChartArtifact[]
  if (isRecord(payload.execution_result)) executionResult.value = payload.execution_result as unknown as ExecutionResult
  if (typeof payload.execution_path === 'string') executionPath.value = payload.execution_path
  if (Array.isArray(payload.sql_queries)) sqlQueries.value = payload.sql_queries.filter(isString)
  if (Array.isArray(payload.generated_code)) generatedCode.value = payload.generated_code.filter(isString)
  if (Array.isArray(payload.sub_questions)) subQuestions.value = payload.sub_questions.filter(isString)
  if (typeof payload.report_markdown === 'string') reportMarkdown.value = payload.report_markdown
  if (['task_completed', 'task_failed', 'task_cancelled'].includes(event.event_type)) {
    running.value = false
    source?.close()
    source = null
    currentTaskId.value = null
  }
  if (event.event_type === 'task_failed' || event.event_type === 'task_cancelled') {
    error.value = event.message
  }
}

async function handleCancel() {
  if (!currentTaskId.value) return
  try {
    await cancelAnalysisTask(currentTaskId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '取消任务失败。'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

onBeforeUnmount(() => {
  source?.close()
})
</script>
