# Contributing

1. Reproduce behavior with pytest or an `agent_eval` case before changing Agent logic.
2. Keep conclusions grounded in real DuckDB or pandas/scipy output.
3. Run backend tests, both Agent evaluations, frontend tests/build, and lint.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe agent_eval\run_batch_eval.py
.venv\Scripts\python.exe agent_eval\enterprise_business_eval.py
cd frontend
npm test
npm run build
```

Do not commit `.env`, uploaded datasets, SQLite files, logs, generated evaluation reports, credentials, or proprietary data. Pull requests should explain the failure mode, new invariant, regression coverage, and security/storage/API impact.
