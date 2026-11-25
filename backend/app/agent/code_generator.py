"""Produces validated, structured file changes from the AI provider."""

from __future__ import annotations

from typing import Any

from app.agent.ai.base import AIResult, parse_changeset
from app.agent.context_builder import RepoContext
from app.agent.models import ChangeSet


class CodeGenerator:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def generate(
        self,
        *,
        task_title: str,
        task_description: str,
        plan: dict[str, Any],
        repo_summary: dict[str, Any],
        context: RepoContext,
        previous_error: str | None = None,
    ) -> tuple[ChangeSet, AIResult]:
        result = await self.provider.generate_changes(
            task_title=task_title,
            task_description=task_description,
            plan=plan,
            repo_summary=repo_summary,
            context=context,
            previous_error=previous_error,
        )
        return parse_changeset(result.content), result
