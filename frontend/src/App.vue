<template>
  <DataAnalystWorkbench v-show="currentView === 'workbench'" @open-log="openLog" @open-ops="currentView = 'ops'" />
  <ImprovementLogView
    v-if="currentView === 'logs'"
    :dataset-id="logContext.datasetId"
    :last-question="logContext.lastQuestion"
    @back="currentView = 'workbench'"
  />
  <AgentOpsView v-if="currentView === 'ops'" @back="currentView = 'workbench'" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AgentOpsView from './views/AgentOpsView.vue'
import DataAnalystWorkbench from './views/DataAnalystWorkbench.vue'
import ImprovementLogView from './views/ImprovementLogView.vue'

interface LogContext {
  datasetId?: string | null
  lastQuestion?: string | null
}

const currentView = ref<'workbench' | 'logs' | 'ops'>('workbench')
const logContext = ref<LogContext>({})

function openLog(context: LogContext) {
  logContext.value = context
  currentView.value = 'logs'
}
</script>
