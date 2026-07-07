# LangGraph Data Analyst Agent Workbench

Portfolio-grade data analysis Agent workbench built with LangGraph, FastAPI, Vue 3, TypeScript, DuckDB, pandas, scipy, ECharts, and SSE.

## What This MVP Shows

- CSV/Excel upload with size and path boundaries.
- Automatic data profiling: schema, missingness, unique counts, numeric stats, outlier hints.
- Structured `AnalysisState` carried through a LangGraph workflow.
- Multi-node agent workflow: load, profile, understand, plan, choose path, execute, chart, insight, review, report.
- Real execution through DuckDB SQL or pandas/scipy, with no arbitrary system command execution.
- Pydantic-validated plan, understanding, result, chart, insight, and review models.
- SSE task stream for frontend timeline updates.
- Traceable Markdown report with SQL/code trace, result tables, chart references, and risk notes.
- Improvement log for recording real usage issues, fixes, status, dataset context, and related analysis questions.
- AgentOps foundation: persistent task records, trace spans, token/cost accounting, tenant/user labels, evaluation runs, and failure-to-improvement-log loop.

## Architecture

```text
frontend Vue workbench
  upload / preview / question / timeline / chart / report
        |
        v
FastAPI routers
  datasets API   analysis task API   improvements API   ops API   SSE stream
        |
        v
services + runtime
  SQLite metadata   improvement logs   agent task/trace/token/eval records   in-memory SSE queue
        |
        v
LangGraph workflow
  load_dataset -> profile_dataset -> understand_question -> plan_analysis
  -> choose_execution_path -> duckdb or pandas -> charts -> insights -> review -> report
```

## Quick Start

### Windows One-Command Dev

```powershell
git clone <repo-url>
cd <repo>
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

Or double-click `start-dev.bat`.

First-time setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Install
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

### Docker Compose

```powershell
docker compose up --build
```

Open http://127.0.0.1:8080/.

### Manual Development

```powershell
uv venv .venv
uv pip install -r requirements.txt

cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

More setup details are in `docs/local_setup.md`.

## Demo Flow

1. Upload `samples/sales_sample.csv`.
2. Ask: `按 region 统计 sales 最高的地区，并生成图表和报告`
3. Watch the SSE timeline complete each LangGraph node.
4. Inspect the ECharts bar chart, result table, and Markdown report.
5. Open `AgentOps` to inspect task trace, token estimates, cost, and evaluation runs.
6. Record a usage issue and its fix in the improvement log.
7. Try pandas/scipy paths:
   - `分析 sales 和 profit 的相关性`
   - `分析 sales 的分布`
   - `检测 profit 的异常值`

## Validation

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python agent_eval\run_batch_eval.py
.venv\Scripts\python agent_eval\enterprise_business_eval.py

cd frontend
npm run build
```

Current validation:

- Backend tests: `26 passed`
- Agent batch evaluation: `14 passed`
- Enterprise business evaluation: `8/8 passed`
- Frontend build: passed

## AgentOps Foundation

- `GET /api/ops/summary`: task counts, token total, estimated cost, latest evaluation run.
- `GET /api/ops/tasks`: persisted analysis tasks with `tenant_id`, `user_id`, `trace_id`, status, token budget, and final state.
- `GET /api/ops/tasks/{task_id}`: task detail with trace spans and token usage records.
- `GET /api/ops/eval-runs`: stored batch evaluation reports.
- `POST /api/ops/eval-runs/import`: import `agent_eval/results/latest_eval.json` without running shell commands.
- `agent_eval/run_batch_eval.py`: automatically persists evaluation reports and writes failed cases to the improvement log.

## Agent Handoff Testing

Use `AGENT_HANDOFF.md` when handing this project to another testing Agent. The project also includes:

- `agent_eval/cases.json`: batch natural-language evaluation cases.
- `agent_eval/run_batch_eval.py`: direct LangGraph workflow evaluator.
- `agent_eval/enterprise_business_eval.py`: enterprise dataset evaluator for MRR scope, data quality, invoice risk, health correlations, and CRM Pipeline.
- `scripts/create_agent_bundle.ps1`: creates a clean handoff zip without `.venv`, `node_modules`, SQLite data, logs, or uploaded user datasets.
  Use `-ExtraDatasetZip <zip>` to include a separate external evaluation dataset under `external_eval_data/`.
- `docs/optimization_backlog.md`: correctness-focused optimization backlog derived from the business evaluation plan.

## Safety Boundaries

- Uploaded files are stored only under `backend/data/uploads`.
- Dataset reads reject paths outside the upload directory.
- Upload size is limited by `MAX_UPLOAD_BYTES` defaults to 20 MB.
- DuckDB execution accepts only single SELECT statements and blocks file/system operations.
- pandas execution is implemented as fixed tool functions, not arbitrary generated Python.
- LLM use is optional. Unless `USE_LLM=true` and `OPENAI_API_KEY` are both set, deterministic rule parsing is used.
- If an LLM is enabled, its output is parsed into Pydantic models and sanitized against real dataset columns.

## Open Source Notes

- Do not commit real `.env` files, uploaded datasets, SQLite runtime data, logs, generated handoff zips, or personal documents.
- `.env.example` is safe to commit and keeps `USE_LLM=false` by default, so local tests do not consume OpenAI tokens.
- Sample and evaluation CSV files in `samples/` and `agent_eval/fixtures/` are synthetic demo data.
- Large or private evaluation datasets should be distributed outside the repository, for example through a separate release artifact or private handoff package.

## License

MIT.
