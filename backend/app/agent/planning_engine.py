"""Wraps the AI provider to produce a validated implementation plan."""

from __future__ import annotations

from typing import Any

from app.agent.ai.base import AIResult, parse_plan
from app.agent.context_builder import RepoContext
from app.agent.models import ImplementationPlan


class PlanningEngine:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def analyze(
        self,
        *,
        task_title: str,
        task_description: str,
        repo_summary: dict[str, Any],
        context: RepoContext,
    ) -> AIResult:
        return await self.provider.analyze_task(
            task_title=task_title,
            task_description=task_description,
            repo_summary=repo_summary,
            context=context,
        )

    async def create_plan(
        self,
        *,
        task_title: str,
        task_description: str,
        repo_summary: dict[str, Any],
        context: RepoContext,
        analysis: str | None = None,
    ) -> tuple[ImplementationPlan, AIResult]:
        result = await self.provider.generate_plan(
            task_title=task_title,
            task_description=task_description,
            repo_summary=repo_summary,
            context=context,
            analysis=analysis,
        )
        return parse_plan(result.content), result
