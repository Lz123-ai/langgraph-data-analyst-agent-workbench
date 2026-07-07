<template>
  <section class="panel dataset-preview">
    <div class="panel-title">
      <TableProperties :size="18" />
      <span>数据样例</span>
    </div>

    <div v-if="dataset && profile" class="profile-strip compact-profile-strip">
      <div>
        <strong>{{ dataset.original_filename }}</strong>
        <span>预览前 {{ rows.length }} 行 · 全量 {{ profile.row_count }} 行</span>
      </div>
    </div>
    <p v-else class="empty-text">上传数据集后，可查看样例行。</p>

    <div v-if="rows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in rows" :key="rowIndex">
            <td v-for="column in columns" :key="column">{{ formatCell(row[column]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TableProperties } from '@lucide/vue'
import type { DatasetMetadata, DatasetProfile } from '../api/types'

const props = defineProps<{
  dataset: DatasetMetadata | null
  profile: DatasetProfile | null
  rows: Array<Record<string, unknown>>
}>()

const columns = computed(() => props.dataset?.columns ?? Object.keys(props.rows[0] ?? {}))

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4)
  return String(value)
}

</script>
