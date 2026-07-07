from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.router import router as analysis_router
from app.datasets.router import router as datasets_router
from app.improvements.router import router as improvements_router
from app.ops.router import router as ops_router
from app.improvements.service import improvement_log_service
from app.settings import settings


def create_app() -> FastAPI:
    settings.ensure_directories()
    improvement_log_service.seed_default_logs()
    app = FastAPI(
        title="LangGraph Data Analyst Agent Workbench",
        version="0.1.0",
        description="A portfolio-grade data analysis agent workbench built with LangGraph, FastAPI, and Vue.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(datasets_router)
    app.include_router(analysis_router)
    app.include_router(improvements_router)
    app.include_router(ops_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
