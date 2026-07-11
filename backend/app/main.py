from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.analysis.router import router as analysis_router
from app.analysis.service import analysis_service
from app.database import record_schema_version
from app.datasets.router import router as datasets_router
from app.datasets.service import dataset_service
from app.http_middleware import RequestProtectionMiddleware
from app.improvements.router import router as improvements_router
from app.improvements.service import improvement_log_service
from app.ops.router import router as ops_router
from app.security import require_api_access
from app.settings import settings


def create_app() -> FastAPI:
    settings.validate_deployment()
    settings.ensure_directories()
    record_schema_version(settings.db_path)
    analysis_service.tasks.cleanup_expired(settings.event_retention_days)
    if settings.dataset_retention_days:
        dataset_service.cleanup_expired(settings.dataset_retention_days)
    improvement_log_service.seed_default_logs()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        analysis_service.resume_incomplete()
        yield

    app = FastAPI(
        title="LangGraph Data Analyst Agent Workbench",
        version="0.4.0",
        description="A portfolio-grade data analysis agent workbench built with LangGraph, FastAPI, and Vue.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestProtectionMiddleware)
    protected = [Depends(require_api_access)]
    app.include_router(datasets_router, dependencies=protected)
    app.include_router(analysis_router, dependencies=protected)
    app.include_router(improvements_router, dependencies=protected)
    app.include_router(ops_router, dependencies=protected)

    @app.get("/api/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "auth_required": settings.auth_mode != "local"}

    return app


app = create_app()
