<template>
  <main class="workbench log-page">
    <header class="topbar">
      <div>
        <h1>改进日志</h1>
        <p>记录真实使用中发现的问题、解决措施和后续状态。</p>
      </div>
      <button class="nav-button" @click="$emit('back')">
        <ArrowLeft :size="16" />
        <span>返回工作台</span>
      </button>
    </header>

    <div class="log-page-content">
      <ImprovementLogPanel :dataset-id="datasetId" :last-question="lastQuestion" />
    </div>
  </main>
</template>

<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'
import ImprovementLogPanel from '../components/ImprovementLogPanel.vue'

defineProps<{
  datasetId?: string | null
  lastQuestion?: string | null
}>()

defineEmits<{ back: [] }>()
</script>
