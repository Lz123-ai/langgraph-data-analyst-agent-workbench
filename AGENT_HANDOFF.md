# Handoff For Another Testing Agent

## Objective

Test this LangGraph Data Analyst Agent Workbench as a portfolio-grade Agent project. Do not only inspect code. Run the automated tests, run the batch natural-language evaluation, then use the UI for a small number of exploratory checks.

## Fast Setup

```powershell
cd "C:\path\to\LangGraph Data Analyst Agent Workbench"

python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

After dependencies are installed, the quickest startup is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

Or double-click `start-dev.bat` on Windows.

Stop services with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

Docker alternative:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8080/`.

## Required Checks

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check backend\app agent_eval
.venv\Scripts\coverage.exe run -m pytest -q
.venv\Scripts\coverage.exe report
.venv\Scripts\python.exe agent_eval\run_batch_eval.py
.venv\Scripts\python.exe agent_eval\enterprise_business_eval.py

cd frontend
npm run build
npm test
npm run test:e2e
cd ..
```

## Manual Smoke Test

Start the services:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173/`.

Smoke-test these workflows:

- Upload `samples/sales_sample.csv`
- Ask a group aggregation question
- Confirm SSE timeline updates
- Confirm chart, result table, and Markdown report render
- Click `日志`, create one improvement log, then return to workbench
- Click `AgentOps`, confirm task records, trace spans, token estimates, cost estimates, and evaluation runs are visible

## What To Look For

- Does the Agent answer the actual question, not only a generic describe?
- Does every conclusion cite real DuckDB or pandas/scipy results?
- Do screenshots show layout overlap or horizontal overflow?
- Do failed cases produce readable errors?
- Are fixes added to `agent_eval/cases.json` or pytest so they stay fixed?
- Does `AgentOps` persist task state, trace, token/cost records, and evaluation runs after each analysis?

## Optional Enterprise Eval Dataset

Some handoff bundles include `external_eval_data/enterprise_agent_eval_dataset_20260703_221458.zip`.
If present, unzip it outside the project or into a temporary folder and use its `README.md`,
`test_questions.md`, and `benchmarks.json` for exploratory testing.

Suggested checks:

- Run `agent_eval\enterprise_business_eval.py --data-dir <unzipped dataset dir>` and expect all enterprise cases to pass.
- Upload the CSV files through the UI instead of placing them in `backend/data/uploads`.
- Ask several questions from `test_questions.md`.
- Compare answers against `benchmarks.json` where expected values exist.
- Record failures in `日志`, and add stable failures to `agent_eval/cases.json` or pytest before fixing.
- Re-run `GET /api/ops/summary` or open `AgentOps` to confirm the test tasks are persisted with trace and token records.

## Data Safety

The handoff bundle intentionally excludes `.venv`, `frontend/node_modules`, `frontend/dist`, logs, `backend/data/app.sqlite`, and uploaded user datasets.
External eval datasets are included only when `scripts/create_agent_bundle.ps1 -ExtraDatasetZip <zip>` is used.
