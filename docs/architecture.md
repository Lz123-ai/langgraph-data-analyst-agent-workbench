# Architecture

## Design goals

1. Ground every conclusion in an uploaded dataset and a reproducible tool result.
2. Prefer explicit refusal or clarification over a plausible but unsupported answer.
3. Keep generated execution inside fixed DuckDB and pandas/scipy tools.
4. Make task progress replayable without treating deterministic payload size as LLM usage.

## Runtime

```text
Vue workbench -> FastAPI task API -> bounded background execution
              -> LangGraph validated state machine
              -> fixed DuckDB / pandas tools
              -> SQLite task_events append-only log
              -> cursor-based SSE replay
```

`runtime_tasks` stores durable status and cancellation intent. `task_events` stores ordered events with `sequence_id`. Every subscriber reads by cursor, so reconnects and multiple viewers do not consume each other's events. Tasks found incomplete after restart are reset safely and rerun with the same task ID; previous partial observability records are cleared before retry.

## Agent boundary

The optional LLM only proposes a structured `QuestionUnderstanding`; its output is sanitized against the real schema. Planning and execution remain validated application code. Rule-only mode uses the same contracts.

## Extension points

- `app/intent`: answerability and schema-value filter resolution.
- `app/graph/planner.py`, `insight.py`, `review.py`, and `report.py`: workflow responsibilities separated from execution tools.
- `BusinessTemplateRegistry`: handlers registered by stable template ID.
- `AnalysisOperation`: validated plan DSL shared by execution paths.
- `agent_eval`: numeric, grounding, robustness, and safety assertions.

SQLite is the reference local adapter. Production deployments can replace it with PostgreSQL and a worker queue while preserving task/event cursor semantics.

The local database records `PRAGMA user_version` and a `schema_migrations` ledger. Table initializers are forward-compatible for the bundled SQLite adapter; deployments that need reversible migrations should use the documented PostgreSQL adapter boundary and a dedicated migration tool.
