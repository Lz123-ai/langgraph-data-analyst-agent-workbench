<template>
  <main v-if="!healthLoaded" class="workbench auth-gate">
    <section class="panel auth-panel"><p>正在连接本地分析服务…</p></section>
  </main>
  <main v-else-if="authRequired && !authenticated" class="workbench auth-gate">
    <section class="panel auth-panel">
      <h1>访问受保护</h1>
      <p>该部署启用了共享访问令牌或 OIDC。Access Token 只保存在当前浏览器会话中。</p>
      <input v-model="tokenInput" type="password" autocomplete="current-password" placeholder="Access Token" @keyup.enter="authenticate" />
      <button class="primary-button" :disabled="authenticating || !tokenInput.trim()" @click="authenticate">
        {{ authenticating ? '验证中' : '进入工作台' }}
      </button>
      <p v-if="authError" class="error-banner">{{ authError }}</p>
    </section>
  </main>
  <DataAnalystWorkbench v-else v-show="currentView === 'workbench'" @open-log="openLog" @open-ops="currentView = 'ops'" />
  <ImprovementLogView
    v-if="healthLoaded && authenticated && currentView === 'logs'"
    :dataset-id="logContext.datasetId"
    :last-question="logContext.lastQuestion"
    @back="currentView = 'workbench'"
  />
  <AgentOpsView v-if="healthLoaded && authenticated && currentView === 'ops'" @back="currentView = 'workbench'" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { API_BASE, apiHeaders, hasApiAccessToken, setApiAccessToken } from './api/client'
import AgentOpsView from './views/AgentOpsView.vue'
import DataAnalystWorkbench from './views/DataAnalystWorkbench.vue'
import ImprovementLogView from './views/ImprovementLogView.vue'

interface LogContext {
  datasetId?: string | null
  lastQuestion?: string | null
}

const currentView = ref<'workbench' | 'logs' | 'ops'>('workbench')
const logContext = ref<LogContext>({})
const authRequired = ref(false)
const authenticated = ref(hasApiAccessToken())
const authenticating = ref(false)
const authError = ref<string | null>(null)
const tokenInput = ref('')
const healthLoaded = ref(false)

function openLog(context: LogContext) {
  logContext.value = context
  currentView.value = 'logs'
}

async function authenticate() {
  authenticating.value = true
  authError.value = null
  setApiAccessToken(tokenInput.value)
  try {
    const response = await fetch(`${API_BASE}/api/ops/summary`, { headers: apiHeaders() })
    if (!response.ok) throw new Error('Token 无效。')
    authenticated.value = true
    tokenInput.value = ''
  } catch (error) {
    setApiAccessToken('')
    authenticated.value = false
    authError.value = error instanceof Error ? error.message : '验证失败。'
  } finally {
    authenticating.value = false
  }
}

onMounted(async () => {
  try {
    const response = await fetch(`${API_BASE}/api/health`)
    if (response.ok) {
      const health = await response.json()
      authRequired.value = Boolean(health.auth_required)
      authenticated.value = !authRequired.value || hasApiAccessToken()
    }
  } catch {
    authError.value = '无法连接后端服务。'
  } finally {
    healthLoaded.value = true
  }
})
</script>

<style scoped>
.auth-gate {
  display: grid;
  min-height: 100vh;
  place-items: center;
}

.auth-panel {
  display: grid;
  gap: 16px;
  width: min(460px, 100%);
}

.auth-panel h1,
.auth-panel p {
  margin: 0;
}

.auth-panel input {
  width: 100%;
  border: 1px solid #cbd5df;
  border-radius: 7px;
  padding: 11px 12px;
}
</style>
