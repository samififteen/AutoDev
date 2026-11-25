"""AI provider abstraction and deterministic JSON parsing helpers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agent.ai import prompts
from app.agent.models import ChangeSet, FailureAnalysis, ImplementationPlan, PRSummary

if TYPE_CHECKING:
    from app.agent.context_builder import RepoContext


class AIProviderError(RuntimeError):
    """The provider failed, returned malformed output, or is unavailable."""


class DemoFixtureError(AIProviderError):
    """The deterministic demo provider has no fixture for this task."""


@dataclass(slots=True)
class AIUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(slots=True)
class AIResult:
    content: str
    provider: str
    model: str
    usage: AIUsage = field(default_factory=AIUsage)
    fixture: bool = False


class AIProvider(ABC):
    name = "base"
    model = "unknown"
    is_fixture = False

    @abstractmethod
    async def _complete(self, messages: list[dict[str, str]], *, json_mode: bool = True) -> AIResult:
        raise NotImplementedError

    async def analyze_task(
        self,
        *,
        task_title: str,
        task_description: str,
        repo_summary: dict[str, Any],
        context: RepoContext,
    ) -> AIResult:
        return await self._complete(
            prompts.build_task_messages(
                task_title=task_title,
                task_description=task_description,
                repo_summary=repo_summary,
                context=context.render(),
            )
        )

    async def generate_plan(
        self,
        *,
        task_title: str,
        task_description: str,
        repo_summary: dict[str, Any],
        context: RepoContext,
        analysis: str | None = None,
    ) -> AIResult:
        return await self._complete(
            prompts.build_plan_messages(
                task_title=task_title,
                task_description=task_description,
                repo_summary=repo_summary,
                context=context.render(),
                analysis=analysis,
            )
        )

    async def generate_changes(
        self,
        *,
        task_title: str,
        task_description: str,
        plan: dict[str, Any],
        repo_summary: dict[str, Any],
        context: RepoContext,
        previous_error: str | None = None,
    ) -> AIResult:
        return await self._complete(
            prompts.build_changes_messages(
                task_title=task_title,
                task_description=task_description,
                plan=plan,
                repo_summary=repo_summary,
                context=context.render(),
                previous_error=previous_error,
            )
        )

    async def analyze_failure(
        self,
        *,
        task_title: str,
        test_output: str,
        failing_tests: list[str],
        plan: dict[str, Any],
        context: RepoContext,
        attempt: int,
        max_attempts: int,
    ) -> AIResult:
        return await self._complete(
            prompts.build_failure_messages(
                task_title=task_title,
                test_output=test_output,
                failing_tests=failing_tests,
                plan=plan,
                context=context.render(),
                attempt=attempt,
                max_attempts=max_attempts,
            )
        )

    async def summarize_changes(
        self,
        *,
        task_title: str,
        files: list[dict[str, Any]],
        tests: list[dict[str, Any]],
        validation: dict[str, Any],
        provider_note: str,
    ) -> AIResult:
        return await self._complete(
            prompts.build_pr_messages(
                task_title=task_title,
                files=files,
                tests=tests,
                validation=validation,
                provider_note=provider_note,
            )
        )

    async def aclose(self) -> None:
        """Release network resources, if any."""
        return None


# --------------------------------------------------------------------------- #
# Parsing / validation of model output
# --------------------------------------------------------------------------- #
_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract exactly one JSON object from a model response."""
    if not text or not text.strip():
        raise AIProviderError("The AI provider returned an empty response")
    candidates: list[str] = [text.strip()]
    candidates.extend(match.group(1) for match in _FENCE.finditer(text))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AIProviderError("The AI provider did not return valid JSON")


def parse_plan(text: str) -> ImplementationPlan:
    data = extract_json_object(text)
    steps = data.get("steps")
    if isinstance(steps, list):
        normalized = []
        for step in steps:
            if isinstance(step, str):
                normalized.append({"title": step})
            elif isinstance(step, dict):
                normalized.append(step)
        data["steps"] = normalized
    try:
        return ImplementationPlan.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise AIProviderError(f"The AI plan did not match the expected structure: {exc}") from exc


def parse_changeset(text: str) -> ChangeSet:
    data = extract_json_object(text)
    edits = data.get("edits") or data.get("changes") or []
    data["edits"] = edits
    try:
        changeset = ChangeSet.model_validate(data)
    except Exception as exc:
        raise AIProviderError(f"The AI change set did not match the expected structure: {exc}") from exc
    for edit in changeset.edits:
        if edit.operation in {"create", "update"} and edit.content is None:
            raise AIProviderError(f"Edit for '{edit.path}' is missing full file content")
    return changeset


def parse_failure_analysis(text: str) -> FailureAnalysis:
    data = extract_json_object(text)
    if "changes" not in data and "edits" in data:
        data["changes"] = data["edits"]
    data.setdefault("analysis", "No diagnosis returned")
    try:
        return FailureAnalysis.model_validate(data)
    except Exception as exc:
        raise AIProviderError(f"The failure analysis did not match the expected structure: {exc}") from exc


def parse_pr_summary(text: str) -> PRSummary:
    data = extract_json_object(text)
    try:
        return PRSummary.model_validate(data)
    except Exception as exc:
        raise AIProviderError(f"The PR summary did not match the expected structure: {exc}") from exc
