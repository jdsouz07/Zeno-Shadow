"""Settings loaded from .env (no third-party dependencies)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines into os.environ without overriding existing variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass
class Settings:
    api_key: str
    base_url: str
    models: dict[str, str]
    providers: dict[str, str]
    allow_fallbacks: bool
    temperature: float
    max_tokens: int
    reasoning: bool
    reasoning_effort: str | None
    budget_total_usd: float
    budget_per_run_usd: float
    log_dir: Path


def get_settings() -> Settings:
    load_dotenv()
    env = os.environ
    return Settings(
        api_key=env.get("OPENROUTER_API_KEY", ""),
        base_url=env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        models={
            "main": env.get("MODEL_MAIN", "deepseek/deepseek-v4-flash-0731"),
            "pro": env.get("MODEL_PRO", "deepseek/deepseek-v4-pro-0813"),
            "compare": env.get("MODEL_COMPARE", "deepseek/deepseek-v3.2"),
            "persuader": env.get("MODEL_PERSUADER", "openai/gpt-6-sol"),
        },
        providers={
            "main": env.get("PROVIDER_MAIN", "deepinfra/fp8"),
            "pro": env.get("PROVIDER_PRO", "deepseek"),
            "compare": env.get("PROVIDER_COMPARE", "deepinfra/fp4"),
            "persuader": env.get("PROVIDER_PERSUADER", "openai"),
        },
        allow_fallbacks=env.get("ALLOW_FALLBACKS", "false").lower() == "true",
        temperature=float(env.get("TEMPERATURE", "1.0")),
        max_tokens=int(env.get("MAX_TOKENS", "4000")),
        reasoning=env.get("REASONING", "on").lower() in ("on", "true", "1"),
        reasoning_effort=env.get("REASONING_EFFORT") or None,
        budget_total_usd=float(env.get("BUDGET_TOTAL_USD", "45")),
        budget_per_run_usd=float(env.get("BUDGET_PER_RUN_USD", "0.75")),
        log_dir=ROOT / env.get("LOG_DIR", "runs"),
    )
