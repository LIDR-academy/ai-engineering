"""
LAYER: services (provider abstraction)
RESPONSIBILITY: Strategy Pattern for LLM provider instantiation.
WHY IT EXISTS: Decouples provider details from business logic so new
               providers (OpenAI, Anthropic) can be added without touching
               llm_service.py. Required for Session 3 provider abstraction.
DEPENDS ON: app.config (settings, get_model_config)
"""

from abc import ABC, abstractmethod
from typing import Literal

from app.config import get_model_config

ProviderName = Literal["deepseek", "kimi"]


class LLMProvider(ABC):
    """Abstract strategy for LLM providers."""

    @abstractmethod
    def get_client_and_model(self, tier: str):
        """Return (client, model_name) tuple."""


class DeepSeekProvider(LLMProvider):
    """DeepSeek strategy."""

    def get_client_and_model(self, tier: str):
        # get_model_config already handles deepseek tiers
        return get_model_config(tier)


class KimiProvider(LLMProvider):
    """Kimi (Moonshot AI) strategy."""

    def get_client_and_model(self, tier: str):
        # get_model_config already handles kimi tiers
        return get_model_config(tier)


_PROVIDERS: dict[ProviderName, LLMProvider] = {
    "deepseek": DeepSeekProvider(),
    "kimi": KimiProvider(),
}


def get_provider(name: ProviderName) -> LLMProvider:
    """
    Factory: returns the provider strategy for the given name.
    WHY factory: Centralizes provider registration in one dict.
    """
    if name not in _PROVIDERS:
        raise ValueError(f"Proveedor desconocido: {name}")
    return _PROVIDERS[name]
