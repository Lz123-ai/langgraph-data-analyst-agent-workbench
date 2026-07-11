# Agent Evaluation Handoff

This directory lets another Agent test the project without manually clicking through the UI.

## Run

From the repository root:

```powershell
.venv\Scripts\python.exe agent_eval\run_batch_eval.py
```

The script:

- copies the fixture dataset into `backend/data/uploads`
- invokes the LangGraph workflow directly
- checks execution path, result type, key rows, metrics, and report keywords
- writes a JSON report under `agent_eval/results/`
- exits with code `1` if any case fails
- includes unsupported prediction, causality, out-of-domain, and profiled-value filter regressions

## Add More Cases

Edit `agent_eval/cases.json`. Useful assertions:

- `expected_kind`
- `expected_path`
- `first_row_contains`
- `any_row_contains`
- `metrics_contains`
- `report_keywords`

When a real user question fails, add it here before fixing the agent. The fixed behavior should then become a permanent regression case.

## Enterprise Dataset Evaluation

When the external enterprise dataset is available, run:

```powershell
.venv\Scripts\python.exe agent_eval\enterprise_business_eval.py
```

The script auto-detects either:

- `external_eval_data/enterprise_agent_eval_dataset_20260703_221458.zip`
- `.run/enterprise_eval_dataset/enterprise_agent_eval_dataset_20260703_221458`

It validates MRR period scope, high-risk ranking, customer success priority, expansion/contraction, health correlations, data quality, invoice risk, and CRM Pipeline analysis.
