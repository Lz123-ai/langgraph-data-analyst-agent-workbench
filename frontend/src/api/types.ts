export interface DatasetMetadata {
  dataset_id: string
  original_filename: string
  stored_filename: string
  file_path: string
  file_type: 'csv' | 'excel'
  size_bytes: number
  row_count: number
  column_count: number
  columns: string[]
  created_at: string
}

export interface ColumnProfile {
  name: string
  dtype: string
  logical_type: string
  missing_count: number
  missing_rate: number
  unique_count: number
  sample_values: unknown[]
  min?: unknown
  max?: unknown
  mean?: number
  std?: number
  q1?: number
  q3?: number
  outlier_count?: number
  top_values: Array<{ value: unknown; count: number }>
}

export interface DataGrainProfile {
  grain_type: string
  grain_columns: string[]
  primary_key_candidates: string[][]
  time_field?: string | null
  time_range: Record<string, unknown>
  duplicate_key_count: number
  notes: string[]
}

export interface DatasetProfile {
  dataset_id?: string
  row_count: number
  column_count: number
  columns: ColumnProfile[]
  numeric_columns: string[]
  categorical_columns: string[]
  datetime_columns: string[]
  boolean_columns: string[]
  grain?: DataGrainProfile | null
  generated_at: string
}

export interface DatasetUploadResponse {
  dataset: DatasetMetadata
  profile: DatasetProfile
  preview: Array<Record<string, unknown>>
}

export interface DatasetPreviewResponse {
  dataset_id: string
  columns: string[]
  rows: Array<Record<string, unknown>>
}

export interface ExecutionTable {
  name: string
  columns: string[]
  rows: Array<Record<string, unknown>>
}

export interface ExecutionResult {
  kind: string
  source: string
  tables: ExecutionTable[]
  metrics: Record<string, unknown>
  method: string
}

export interface ChartArtifact {
  chart_id: string
  title: string
  chart_type: string
  echarts_option: Record<string, unknown>
  evidence_table?: string
}

export interface TaskEvent {
  event_id: string
  task_id: string
  event_type: string
  status: string
  timestamp: string
  node?: string
  message: string
  payload: Record<string, unknown>
}

export interface AnalysisTaskResponse {
  task_id: string
  status: string
}

export type ImprovementStatus = 'open' | 'resolved' | 'monitoring'

export interface ImprovementLogEntry {
  log_id: string
  issue: string
  resolution: string
  status: ImprovementStatus
  dataset_id?: string | null
  related_question?: string | null
  created_at: string
  updated_at: string
}

export interface ImprovementLogCreate {
  issue: string
  resolution: string
  status: ImprovementStatus
  dataset_id?: string | null
  related_question?: string | null
}

export interface ImprovementLogListResponse {
  logs: ImprovementLogEntry[]
}

export interface AgentTaskRecord {
  task_id: string
  trace_id: string
  tenant_id: string
  user_id: string
  dataset_id: string
  question: string
  status: string
  model_name?: string | null
  prompt_version?: string | null
  token_budget?: number | null
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  started_at?: string | null
  completed_at?: string | null
  duration_ms?: number | null
  error?: string | null
  final_state?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface TraceSpanRecord {
  span_id: string
  trace_id: string
  task_id: string
  parent_span_id?: string | null
  span_type: string
  name: string
  status: string
  started_at: string
  ended_at?: string | null
  duration_ms?: number | null
  input_summary?: string | null
  output_summary?: string | null
  metadata: Record<string, unknown>
  error?: string | null
}

export interface TokenUsageRecord {
  usage_id: string
  trace_id: string
  task_id: string
  node?: string | null
  model_name: string
  prompt_version: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  source: string
  created_at: string
}

export interface EvalRunRecord {
  eval_run_id: string
  status: string
  total: number
  passed: number
  failed: number
  source_path?: string | null
  result_json: Record<string, unknown>
  created_at: string
}

export interface AgentOpsSummary {
  task_count: number
  running_count: number
  succeeded_count: number
  failed_count: number
  total_tokens: number
  estimated_cost_usd: number
  latest_eval?: EvalRunRecord | null
}

export interface AgentTaskListResponse {
  tasks: AgentTaskRecord[]
}

export interface AgentTaskDetailResponse {
  task: AgentTaskRecord
  trace: TraceSpanRecord[]
  token_usage: TokenUsageRecord[]
}

export interface EvalRunListResponse {
  eval_runs: EvalRunRecord[]
}
