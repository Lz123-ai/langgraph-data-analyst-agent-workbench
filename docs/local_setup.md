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

## Environment Variables

Copy `.env.example` to `.env` only when you need custom values:

```powershell
Copy-Item .env.example .env
```

The app works without an OpenAI API key because deterministic rule-based parsing is enabled by default.
To enable LLM-based understanding:

```env
USE_LLM=true
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe agent_eval\run_batch_eval.py
cd frontend
npm run build
```

Expected baseline:

- Backend tests pass.
- Batch Agent evaluation passes.
- Frontend production build passes.
