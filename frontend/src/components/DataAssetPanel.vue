<template>
  <section class="panel asset-panel">
    <div class="panel-title-row">
      <div>
        <Database :size="18" />
        <span>数据资产</span>
      </div>
      <span v-if="dataset" class="mini-chip">{{ dataset.file_type.toUpperCase() }}</span>
    </div>

    <div v-if="dataset && profile" class="asset-summary">
      <strong>{{ dataset.original_filename }}</strong>
      <span>{{ formatBytes(dataset.size_bytes) }} · {{ formatDate(dataset.created_at) }}</span>
    </div>

    <div v-if="profile" class="metric-grid">
      <div class="metric-card">
        <span>记录数</span>
        <strong>{{ profile.row_count }}</strong>
      </div>
      <div class="metric-card">
        <span>字段数</span>
        <strong>{{ profile.column_count }}</strong>
      </div>
      <div class="metric-card">
        <span>数值</span>
        <strong>{{ profile.numeric_columns.length }}</strong>
      </div>
      <div class="metric-card">
        <span>类别</span>
        <strong>{{ profile.categorical_columns.length }}</strong>
      </div>
    </div>
    <p v-else class="empty-text">上传数据后，这里会展示数据资产、字段结构与质量概览。</p>

    <div v-if="profile?.grain" class="grain-box platform-grain">
      <strong>{{ profile.grain.grain_type }}</strong>
      <span v-if="profile.grain.grain_columns.length">粒度：{{ profile.grain.grain_columns.join(' + ') }}</span>
      <span v-if="profile.grain.time_field">时间：{{ profile.grain.time_field }}</span>
      <span v-if="profile.grain.duplicate_key_count">重复粒度：{{ profile.grain.duplicate_key_count }}</span>
    </div>

    <div v-if="profile" class="field-table">
      <div class="field-table-head">
        <span>字段</span>
        <span>类型</span>
        <span>缺失</span>
      </div>
      <button
        v-for="column in profile.columns"
        :key="column.name"
        class="field-row"
        :class="qualityClass(column.missing_rate)"
        :title="column.sample_values?.length ? `样例：${column.sample_values.join('，')}` : column.name"
        type="button"
      >
        <span>{{ column.name }}</span>
        <small>{{ logicalTypeLabel(column.logical_type) }}</small>
        <strong>{{ Math.round(column.missing_rate * 100) }}%</strong>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Database } from '@lucide/vue'
import type { DatasetMetadata, DatasetProfile } from '../api/types'

defineProps<{
  dataset: DatasetMetadata | null
  profile: DatasetProfile | null
}>()

function logicalTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    numeric: '数值',
    categorical: '类别',
    datetime: '时间',
    boolean: '布尔',
    text: '文本',
    unknown: '未知'
  }
  return labels[type] ?? type
}

function qualityClass(missingRate: number): string {
  if (missingRate >= 0.2) return 'field-risk-high'
  if (missingRate > 0) return 'field-risk-warning'
  return 'field-risk-ok'
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString()
}
</script>
