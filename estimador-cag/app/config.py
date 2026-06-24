"""
LAYER: config (settings & wiring)
RESPONSIBILITY: Load environment variables, validate them via Pydantic, and define tier routing
WHY IT EXISTS: Prevents secret leakage into source code and centralizes environment-dependent
               configuration. Fails fast on startup if configuration is invalid.
DEPENDS ON: pydantic_settings (BaseSettings), openai (OpenAI client factory)
"""

from typing import Literal

from openai import OpenAI
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TierName = Literal["flash", "pro", "backup", "backup_pro"]


class Settings(BaseSettings):
    """Pydantic Settings validates env vars at import time. Fails fast on missing secrets."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_tier: TierName = "flash"

    deepseek_api_key: str = "dummy"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_model_pro: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    kimi_api_key: str = "dummy"
    kimi_model: str = "kimi-k2.5"
    kimi_model_pro: str = "kimi-k2.6"
    kimi_base_url: str = "https://api.moonshot.ai/v1"

    database_url: str = "postgresql://dev:dev@localhost:5432/lidr"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 86400

    semantic_cache_mode: Literal["off", "shadow", "serve"] = "shadow"
    semantic_cache_threshold: float = 0.85
    stress_fake_provider: bool = False

    @model_validator(mode="after")
    def validate_api_keys(self):
        """Fail-fast automatico: si ambas keys son dummy, la app no arranca."""
        if (
            not self.stress_fake_provider
            and self.deepseek_api_key == "dummy"
            and self.kimi_api_key == "dummy"
        ):
            raise ValueError(
                "Al menos una API key debe configurarse: DEEPSEEK_API_KEY o KIMI_API_KEY"
            )
        return self

    @property
    def tier_ladder(self) -> list[TierName]:
        """Ordered list of tiers for escalation logic."""
        return ["flash", "pro", "backup", "backup_pro"]


settings = Settings()


def get_model_config(tier: TierName | None = None) -> tuple[OpenAI, str]:
    """Factory: returns an (OpenAI-compatible client, model_name) tuple."""
    tier = tier or settings.llm_tier

    if tier == "flash":
        client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
        return client, settings.deepseek_model
    elif tier == "pro":
        client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
        return client, settings.deepseek_model_pro
    elif tier == "backup":
        return (
            OpenAI(api_key=settings.kimi_api_key, base_url=settings.kimi_base_url),
            settings.kimi_model,
        )
    elif tier == "backup_pro":
        return (
            OpenAI(api_key=settings.kimi_api_key, base_url=settings.kimi_base_url),
            settings.kimi_model_pro,
        )
    else:
        raise ValueError(f"Tier desconocido: {tier}")
