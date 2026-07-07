<template>
  <section class="panel report-panel">
    <div class="panel-title">
      <FileText :size="18" />
      <span>可追溯 Markdown 报告</span>
    </div>
    <article v-if="html" class="markdown-body" v-html="html" />
    <p v-else class="empty-text">最终报告会引用 SQL、pandas 代码、结果表、图表和风险提示。</p>
  </section>
</template>

<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'
import { FileText } from '@lucide/vue'

const props = defineProps<{ markdown: string | null }>()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const html = computed(() => (props.markdown ? md.render(props.markdown) : ''))
</script>
