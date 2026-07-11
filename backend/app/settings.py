from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load the repository .env without overriding explicit process variables."""
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


class Settings:
    root_dir: Path = Path(__file__).resolve().parents[2]
    backend_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = backend_dir / "data"
    upload_dir: Path = data_dir / "uploads"
    db_path: Path = data_dir / "app.sqlite"
    app_environment: str = os.getenv("APP_ENV", "development").lower()
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    trusted_hosts: list[str] = [
        host.strip()
        for host in os.getenv("TRUSTED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
        if host.strip()
    ]
    rate_limit_requests: int = max(1, int(os.getenv("RATE_LIMIT_REQUESTS", "120")))
    rate_limit_window_seconds: int = max(1, int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")))
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_model: str = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    llm_base_url: str | None = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None
    openai_model: str = llm_model  # backwards-compatible AgentOps field
    use_llm: bool = os.getenv("USE_LLM", "false").lower() == "true" and (
        llm_api_key is not None or llm_provider.lower() == "ollama"
    )
    prompt_version: str = os.getenv("PROMPT_VERSION", "rule-first-v1")
    default_token_budget: int = int(os.getenv("DEFAULT_TOKEN_BUDGET", "50000"))
    input_token_price_per_1k: float = float(os.getenv("INPUT_TOKEN_PRICE_PER_1K", "0.00015"))
    output_token_price_per_1k: float = float(os.getenv("OUTPUT_TOKEN_PRICE_PER_1K", "0.0006"))
    api_access_token: str | None = os.getenv("API_ACCESS_TOKEN") or None
    auth_mode: str = os.getenv("AUTH_MODE", "token" if api_access_token else "local").lower()
    oidc_issuer: str | None = os.getenv("OIDC_ISSUER") or None
    oidc_audience: str | None = os.getenv("OIDC_AUDIENCE") or None
    oidc_jwks_url: str | None = os.getenv("OIDC_JWKS_URL") or None
    oidc_tenant_claim: str = os.getenv("OIDC_TENANT_CLAIM", "tenant_id")
    oidc_algorithms: list[str] = [
        item.strip() for item in os.getenv("OIDC_ALGORITHMS", "RS256").split(",") if item.strip()
    ]
    max_dataset_rows: int = int(os.getenv("MAX_DATASET_ROWS", "250000"))
    max_dataset_columns: int = int(os.getenv("MAX_DATASET_COLUMNS", "200"))
    max_result_rows: int = int(os.getenv("MAX_RESULT_ROWS", "200"))
    max_concurrent_tasks: int = max(1, int(os.getenv("MAX_CONCURRENT_TASKS", "2")))
    task_timeout_seconds: int = max(5, int(os.getenv("TASK_TIMEOUT_SECONDS", "120")))
    event_retention_days: int = max(1, int(os.getenv("EVENT_RETENTION_DAYS", "7")))
    dataset_retention_days: int = max(0, int(os.getenv("DATASET_RETENTION_DAYS", "0")))
    trace_include_sample_data: bool = os.getenv("TRACE_INCLUDE_SAMPLE_DATA", "false").lower() == "true"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_deployment(self) -> None:
        """Fail closed for deployment-only misconfiguration, while preserving local-first development."""
        if self.app_environment not in {"development", "test", "production"}:
            raise RuntimeError("APP_ENV must be development, test, or production.")
        if self.auth_mode not in {"local", "token", "oidc"}:
            raise RuntimeError("AUTH_MODE must be local, token, or oidc.")
        if self.auth_mode == "token" and not self.api_access_token:
            raise RuntimeError("API_ACCESS_TOKEN is required when AUTH_MODE=token.")
        if self.auth_mode == "oidc" and not (self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url):
            raise RuntimeError("OIDC_ISSUER, OIDC_AUDIENCE, and OIDC_JWKS_URL are required when AUTH_MODE=oidc.")
        if self.app_environment == "production":
            if self.auth_mode == "local":
                raise RuntimeError("AUTH_MODE=local is not allowed when APP_ENV=production.")
            if "*" in self.cors_origins:
                raise RuntimeError("Wildcard CORS is not allowed when APP_ENV=production.")


settings = Settings()
