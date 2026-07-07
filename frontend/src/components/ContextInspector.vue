<template>
  <aside class="context-inspector">
    <section class="panel inspector-panel">
      <div class="panel-title">
        <SlidersHorizontal :size="18" />
        <span>任务检查器</span>
      </div>

      <div class="inspector-stat-grid">
        <div>
          <span>执行状态</span>
          <strong>{{ running ? '运行中' : '空闲' }}</strong>
        </div>
        <div>
          <span>结果表</span>
          <strong>{{ result?.tables?.length ?? 0 }}</strong>
        </div>
        <div>
          <span>图表</span>
          <strong>{{ charts.length }}</strong>
        </div>
        <div>
          <span>事件</span>
          <strong>{{ events.length }}</strong>
        </div>
      </div>

      <div class="inspector-section">
        <h3>当前数据集</h3>
        <p v-if="dataset">{{ dataset.original_filename }}</p>
        <p v-else class="empty-text">尚未上传数据集。</p>
      </div>

      <div class="inspector-section">
        <h3>执行口径</h3>
        <div class="detail-strip">
          <span>{{ executionPathLabel }}</span>
          <span>{{ result?.kind ?? '未生成结果' }}</span>
        </div>
      </div>

      <div v-if="subQuestions.length" class="inspector-section">
        <h3>子问题拆分</h3>
        <ol class="sub-question-list">
          <li v-for="(item, index) in subQuestions" :key="`${index}-${item}`">{{ item }}</li>
        </ol>
      </div>

      <div class="inspector-section">
        <h3>证据链</h3>
        <div class="evidence-list">
          <span>{{ sqlQueries.length }} 条 SQL</span>
          <span>{{ generatedCode.length }} 段 pandas / SQL 追踪</span>
          <span>{{ reportReady ? '报告已生成' : '等待报告' }}</span>
        </div>
      </div>

      <div class="inspector-section">
        <h3>最近事件</h3>
        <p v-if="latestEvent">{{ latestEvent.message }}</p>
        <p v-else class="empty-text">暂无执行事件。</p>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SlidersHorizontal } from '@lucide/vue'
import type { ChartArtifact, DatasetMetadata, ExecutionResult, TaskEvent } from '../api/types'

const props = defineProps<{
  dataset: DatasetMetadata | null
  running: boolean
  events: TaskEvent[]
  charts: ChartArtifact[]
  result: ExecutionResult | null
  executionPath: string | null
  sqlQueries: string[]
  generatedCode: string[]
  subQuestions: string[]
  reportReady: boolean
}>()

const latestEvent = computed(() => props.events[props.events.length - 1])
const executionPathLabel = computed(() => {
  const labels: Record<string, string> = {
    duckdb_sql: 'DuckDB SQL',
    pandas: 'pandas/scipy',
    clarification: '需要澄清'
  }
  return props.executionPath ? labels[props.executionPath] ?? props.executionPath : '未选择路径'
})
</script>
