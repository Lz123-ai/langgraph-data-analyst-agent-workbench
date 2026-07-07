.PHONY: install dev stop test eval build docker-up docker-down

install:
	python -m venv .venv
	.venv/Scripts/python.exe -m pip install -r requirements.txt || .venv/bin/python -m pip install -r requirements.txt
	cd frontend && npm install

dev:
	powershell -ExecutionPolicy Bypass -File ./scripts/start-dev.ps1

stop:
	powershell -ExecutionPolicy Bypass -File ./scripts/stop-dev.ps1

test:
	.venv/Scripts/python.exe -m pytest -q || .venv/bin/python -m pytest -q

eval:
	.venv/Scripts/python.exe agent_eval/run_batch_eval.py || .venv/bin/python agent_eval/run_batch_eval.py

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down
