from __future__ import annotations

import os
from pathlib import Path


class Settings:
    backend_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = backend_dir / "data"
    upload_dir: Path = data_dir / "uploads"
    db_path: Path = data_dir / "app.sqlite"
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    use_llm: bool = os.getenv("USE_LLM", "false").lower() == "true" and os.getenv("OPENAI_API_KEY") is not None
    prompt_version: str = os.getenv("PROMPT_VERSION", "rule-first-v1")
    default_token_budget: int = int(os.getenv("DEFAULT_TOKEN_BUDGET", "50000"))
    input_token_price_per_1k: float = float(os.getenv("INPUT_TOKEN_PRICE_PER_1K", "0.00015"))
    output_token_price_per_1k: float = float(os.getenv("OUTPUT_TOKEN_PRICE_PER_1K", "0.0006"))

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
