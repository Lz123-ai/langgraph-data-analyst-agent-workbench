# Local Setup Guide

This project supports three local running modes.

## Option A: Windows Quick Start

First run:

```powershell
cd "C:\path\to\LangGraph Data Analyst Agent Workbench"
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Install
```

Later runs:

```powershell
.\start-dev.bat
```

Stop:

```powershell
.\stop-dev.bat
```

Open:

- Frontend: http://127.0.0.1:5173/
- Backend health: http://127.0.0.1:8000/api/health

## Option B: Manual Development

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Option C: Docker Compose

Docker Compose runs the backend and a production-built frontend.

```powershell
docker compose up --build
```

Open:

- Frontend: http://127.0.0.1:8080/
- Backend health: http://127.0.0.1:8000/api/health

Stop:

```powershell
docker compose down
```

Persistent backend data is stored in the `backend_data` Docker volume.

On Windows without Docker/WSL, open an Administrator PowerShell and run:

```powershell
.\scripts\install-docker-prerequisites.ps1
```

Restart Windows, launch Docker Desktop once, then build and smoke-test both images with:

```powershell
.\scripts\verify-docker.ps1
```

If Docker Hub token requests time out while HTTPS works in the browser, Docker Desktop may not be using the Windows proxy or may be attempting an unavailable IPv6 route. In Docker Desktop settings, configure the same HTTP/HTTPS proxy used by Windows and select IPv4-only networking (or filter IPv6 DNS records), restart Docker Desktop completely, and rerun the verification script.

## Environment Variables

Copy `.env.example` to `.env` only when you need custom values:

```powershell
Copy-Item .env.example .env
```

The app works without an OpenAI API key because deterministic rule-based parsing is enabled by default.
To enable LLM-based understanding:

```env
USE_LLM=true
LLM_PROVIDER=openai_compatible
LLM_MODEL=provider-model-name
LLM_API_KEY=provider-api-key
LLM_BASE_URL=https://provider.example.com/v1
```

OpenAI and local Ollama configurations are documented in [Model Providers](model_providers.md).

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe agent_eval\run_batch_eval.py
cd frontend
npm run build
```

Expected baseline:

- Backend tests: 49 pass with at least 75% source coverage.
- Batch Agent evaluation: 18/18 pass; enterprise evaluation: 8/8 pass.
- Frontend production build passes.
