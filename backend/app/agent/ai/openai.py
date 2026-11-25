"""OpenAI-compatible chat completions provider (works with any compatible API)."""

from __future__ import annotations

from typing import Any

import httpx
from app.agent.ai.base import AIProvider, AIProviderError, AIResult, AIUsage
from app.core.redaction import redact_secrets


class OpenAIProvider(AIProvider):
    name = "openai"
    is_fixture = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise AIProviderError("An AI API key is required for the OpenAI provider")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _complete(self, messages: list[dict[str, str]], *, json_mode: bool = True) -> AIResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = await self._get_client().post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise AIProviderError(f"AI provider request failed: {type(exc).__name__}") from exc

        if response.status_code >= 400:
            detail = redact_secrets(response.text[:500])
            raise AIProviderError(
                f"AI provider returned HTTP {response.status_code}: {detail or 'no detail'}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("AI provider returned an unexpected response shape") from exc

        usage = data.get("usage") or {}
        return AIResult(
            content=content or "",
            provider=self.name,
            model=data.get("model") or self.model,
            usage=AIUsage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            ),
            fixture=False,
        )

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None
