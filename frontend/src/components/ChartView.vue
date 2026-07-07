<template>
  <div ref="el" class="chart-canvas" />
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ option: Record<string, unknown> }>()
const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

onMounted(() => {
  if (!el.value) return
  chart = echarts.init(el.value)
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(
  () => props.option,
  (option) => {
    chart?.setOption(option, true)
  },
  { deep: true }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})

function resize() {
  chart?.resize()
}
</script>
