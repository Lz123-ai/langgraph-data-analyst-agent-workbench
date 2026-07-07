<template>
  <section class="panel chart-panel">
    <div class="panel-title">
      <BarChart3 :size="18" />
      <span>图表与结果</span>
    </div>
    <div v-if="charts.length" class="chart-list">
      <div v-for="chart in charts" :key="chart.chart_id" class="chart-block">
        <div class="chart-head">
          <strong>{{ chart.title }}</strong>
          <small>{{ chartTypeLabel(chart.chart_type) }} | {{ tableNameLabel(chart.evidence_table ?? '') }}</small>
        </div>
        <ChartView v-if="chart.chart_type !== 'table'" :option="chart.echarts_option" />
      </div>
    </div>
    <p v-else class="empty-text">Agent 生成的 ECharts 图表会显示在这里。</p>

    <div v-if="result?.tables?.length" class="result-table">
      <section v-for="table in result.tables" :key="table.name" class="result-table-block">
        <h3>{{ tableNameLabel(table.name) }}</h3>
        <div class="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th v-for="column in table.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in table.rows.slice(0, 20)" :key="index">
              <td v-for="column in table.columns" :key="column">{{ formatCell(row[column]) }}</td>
            </tr>
          </tbody>
        </table>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { BarChart3 } from '@lucide/vue'
import type { ChartArtifact, ExecutionResult } from '../api/types'
import ChartView from './ChartView.vue'

defineProps<{ charts: ChartArtifact[]; result: ExecutionResult | null }>()

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4)
  return String(value)
}

function chartTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    bar: '柱状图',
    line: '折线图',
    scatter: '散点图',
    histogram: '直方图',
    table: '表格'
  }
  return labels[type] ?? type
}

function tableNameLabel(name: string): string {
  const prefixed = name.match(/^q(\d+)_(.+)$/)
  if (prefixed) return `问题 ${prefixed[1]} - ${tableNameLabel(prefixed[2])}`
  const labels: Record<string, string> = {
    group_aggregate: '分组聚合结果',
    count_by_dimension: '维度计数结果',
    time_trend: '时间趋势结果',
    top_records: 'Top 记录结果',
    market_recommendation: '市场扩张建议结果',
    dataset_overview: '数据集概览',
    data_quality_issues: '数据质量问题',
    data_quality_detail_rows: '质量问题明细行',
    mrr_scope_comparison: 'MRR 口径对比',
    monthly_mrr: '月度 MRR',
    risk_customer_ranking: '高风险客户 MRR 排名',
    risk_customer_summary: '风险客户汇总',
    payment_renewal_summary: '账款与续约风险汇总',
    payment_collection_priority: '催收优先级明细',
    customer_success_priority: '客户成功优先级',
    channel_performance_risk: '渠道表现与风险',
    industry_market_selection: '行业市场选择',
    segment_plan_strategy: '分层与套餐策略',
    expansion_contraction_summary: '扩张收缩汇总',
    expansion_contraction_top_expansion: 'Top 扩张客户',
    expansion_contraction_top_contraction: 'Top 收缩客户',
    expansion_contraction_customers: '扩张收缩客户明细',
    health_signal_correlations: '健康信号相关性',
    pipeline_summary: 'Pipeline 汇总',
    pipeline_by_owner: '销售负责人 Pipeline',
    pipeline_by_stage: '销售阶段 Pipeline',
    pipeline_by_type: '商机类型 Pipeline',
    sales_overview_status: '经营总览口径对比',
    order_status_impact: '订单状态影响',
    product_pareto: '商品 Pareto 贡献',
    discount_profit_by_rate: '折扣率与利润率',
    discount_profit_anomalies: '异常折扣订单',
    payment_mix: '支付方式结构',
    sales_channel_strategy: '销售渠道策略',
    correlation_sample: '相关性样本',
    histogram_bins: '分布区间',
    outlier_rows: '异常值记录',
    numeric_describe: '数值描述统计'
  }
  return labels[name] ?? name
}
</script>
