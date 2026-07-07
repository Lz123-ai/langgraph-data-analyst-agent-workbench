<template>
  <section class="panel timeline-panel">
    <div class="panel-title">
      <Workflow :size="18" />
      <span>LangGraph 执行图</span>
    </div>
    <div class="graph-node-grid">
      <div v-for="node in graphNodes" :key="node.id" class="graph-node" :class="nodeStatus(node.id)">
        <span />
        <strong>{{ node.label }}</strong>
      </div>
    </div>
    <ol v-if="events.length" class="timeline">
      <li v-for="event in events" :key="event.event_id" :class="event.status">
        <span class="dot" />
        <div>
          <strong>{{ event.node ? nodeLabel(event.node) : eventTypeLabel(event.event_type) }}</strong>
          <p>{{ event.message }}</p>
          <small>{{ new Date(event.timestamp).toLocaleTimeString() }}</small>
        </div>
      </li>
    </ol>
    <p v-else class="empty-text">Agent 节点事件会通过 SSE 实时显示在这里。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Workflow } from '@lucide/vue'
import type { TaskEvent } from '../api/types'

const props = defineProps<{ events: TaskEvent[]; running?: boolean }>()

const graphNodes = [
  { id: 'load_dataset', label: '读取' },
  { id: 'profile_dataset', label: '画像' },
  { id: 'understand_question', label: '理解' },
  { id: 'plan_analysis', label: '规划' },
  { id: 'choose_execution_path', label: '路由' },
  { id: 'run_sql_analysis', label: 'SQL' },
  { id: 'run_pandas_analysis', label: 'pandas' },
  { id: 'generate_charts', label: '图表' },
  { id: 'generate_insights', label: '洞察' },
  { id: 'review_answer', label: '复核' },
  { id: 'generate_report', label: '报告' }
]

const completedNodes = computed(() => new Set(props.events.filter((event) => event.node).map((event) => event.node as string)))
const failedNodes = computed(
  () => new Set(props.events.filter((event) => event.status === 'failed' && event.node).map((event) => event.node as string))
)

function nodeStatus(node: string): string {
  if (failedNodes.value.has(node)) return 'failed'
  if (completedNodes.value.has(node)) return 'succeeded'
  if (props.running) return 'waiting'
  return ''
}

function nodeLabel(node: string): string {
  const labels: Record<string, string> = {
    load_dataset: '读取数据集',
    profile_dataset: '生成数据画像',
    understand_question: '理解问题',
    plan_analysis: '规划分析',
    choose_execution_path: '选择执行路径',
    run_sql_analysis: '执行 DuckDB SQL',
    run_pandas_analysis: '执行 pandas/scipy',
    generate_charts: '生成图表',
    generate_insights: '生成洞察',
    review_answer: '复核结论',
    generate_report: '生成报告'
  }
  return labels[node] ?? node
}

function eventTypeLabel(eventType: string): string {
  const labels: Record<string, string> = {
    task_started: '任务已开始',
    node_completed: '节点已完成',
    task_completed: '任务已完成',
    task_failed: '任务失败',
    heartbeat: '运行中'
  }
  return labels[eventType] ?? eventType
}
</script>
