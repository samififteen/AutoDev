"""Analyzes failing tests and asks the provider for a minimal correction."""

from __future__ import annotations

from typing import Any

from app.agent.ai.base import AIResult, parse_failure_analysis
from app.agent.context_builder import RepoContext
from app.agent.models import FailureAnalysis


class FailureAnalyzer:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def analyze(
        self,
        *,
        task_title: str,
        test_output: str,
        failing_tests: list[str],
        plan: dict[str, Any],
        context: RepoContext,
        attempt: int,
        max_attempts: int,
    ) -> tuple[FailureAnalysis, AIResult]:
        result = await self.provider.analyze_failure(
            task_title=task_title,
            test_output=test_output,
            failing_tests=failing_tests,
            plan=plan,
            context=context,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        return parse_failure_analysis(result.content), result
