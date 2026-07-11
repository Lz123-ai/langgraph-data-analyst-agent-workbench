# LangGraph Data Analyst Agent Workbench

Local-first, schema-grounded data analysis Agent workbench built with LangGraph, FastAPI, Vue 3, TypeScript, DuckDB, pandas, scipy, ECharts, and replayable SSE.

> **Project boundary:** this repository defaults to a trusted local user and reproducible Agent engineering demonstrations. It does not claim that correlation proves causality, does not silently turn forecasting requests into descriptive statistics, and does not access external knowledge. Shared deployments can use a shared token guard or verified OIDC/JWT identities with tenant/user resource ownership.

## What It Is — And Is Not

- It is a safe tabular analysis workbench with validated plans, fixed execution tools, evidence-linked reports, durable task events, and deterministic regression evaluation.
- It explicitly returns `unanswerable` when a request is out of domain, predictive, causal, unsafe, or unsupported by the uploaded schema.
- It is not an arbitrary Python/SQL execution environment, forecasting platform, causal inference engine, or autonomous web research agent.
- The default mode is single-user and local-first. In `AUTH_MODE=oidc`, tenant/user claims are verified and enforced for datasets, analysis tasks, SSE, and AgentOps resources.

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
- AgentOps foundation: persistent task records, trace spans, provider-reported token usage, deterministic payload metrics, verified ownership labels, evaluation runs, and failure-to-improvement-log loop.

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
  SQLite metadata   improvement logs   durable task/event/trace/usage/eval records
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

- Backend tests: `49 passed`
- Agent batch evaluation: `18 passed`
- Enterprise business evaluation: `8/8 passed`
- Frontend unit test, Playwright upload-to-report E2E, and production build: passed

## AgentOps Foundation

- `GET /api/ops/summary`: task counts, provider-reported token/cost totals, deterministic payload size, and latest evaluation run.
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
- `.env.example` is safe to commit and keeps `USE_LLM=false` by default, so local tests do not consume model tokens.
- Treat a key pasted into chat, an issue, or a commit as compromised: revoke it at the provider and put its replacement only in the ignored `.env` file or a deployment secret store.
- Sample and evaluation CSV files in `samples/` and `agent_eval/fixtures/` are synthetic demo data.
- Large or private evaluation datasets should be distributed outside the repository, for example through a separate release artifact or private handoff package.

## License

MIT.

## Open Source Project Docs

- `docs/architecture.md`: runtime, trust boundaries, and extension points.
- `docs/evaluation.md`: layered Agent evaluation strategy.
- `docs/model_providers.md`: OpenAI, OpenAI-compatible, and Ollama configuration.
- `docs/llm_verification.md`: safe live-provider smoke-test workflow.
- `docs/authentication.md`: local, shared token, and OIDC/JWT modes.
- `docs/threat_model.md`: threats, mitigations, and accepted local-first risks.
- `docs/production_readiness.md`: deployment guardrails, metrics, limits, and the required scaling boundary.
- `CONTRIBUTING.md`: development and regression workflow.
- `SECURITY.md`: supported security boundary and reporting.
- `CHANGELOG.md`: user-visible changes.
