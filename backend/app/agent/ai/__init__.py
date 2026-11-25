"""AI provider factory. Keeps the rest of the agent provider-independent."""

from __future__ import annotations

from app.agent.ai.base import AIProvider, AIProviderError, AIResult, AIUsage
from app.agent.ai.demo import DemoAIProvider
from app.agent.ai.openai import OpenAIProvider
from app.core.config import Settings, get_settings

__all__ = [
    "AIProvider",
    "AIProviderError",
    "AIResult",
    "AIUsage",
    "DemoAIProvider",
    "OpenAIProvider",
    "get_ai_provider",
]


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    if settings.demo_mode or not settings.ai_api_key:
        return DemoAIProvider()
    return OpenAIProvider(
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        base_url=settings.ai_base_url,
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_tokens,
    )
