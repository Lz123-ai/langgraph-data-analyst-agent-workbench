<template>
  <section class="panel question-panel">
    <div class="panel-title">
      <SearchCheck :size="18" />
      <span>分析问题</span>
    </div>
    <textarea
      v-model="question"
      :disabled="disabled || running"
      placeholder="例如：按地区统计销售额最高的前 10 个地区，并生成图表"
    />
    <button class="primary-button" :disabled="disabled || running || question.trim().length < 2" @click="submit">
      <Play :size="16" />
      <span>{{ running ? 'Agent 执行中' : '开始分析' }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Play, SearchCheck } from '@lucide/vue'

defineProps<{ disabled: boolean; running: boolean }>()
const emit = defineEmits<{ run: [question: string] }>()

const question = ref('按 region 统计 sales 最高的地区，并生成图表和报告')

function submit() {
  emit('run', question.value.trim())
}
</script>
