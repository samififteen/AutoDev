from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from app.agent.ai.base import AIResult, AIUsage
from app.agent.ai.demo import DemoAIProvider
from app.agent.git_manager import GitManager
from app.agent.orchestrator import AgentOrchestrator
from app.core.config import get_settings
from app.database.session import session_scope
from app.models import AgentExecution, DevelopmentTask
from app.services.execution_service import build_execution_detail, create_execution
from sqlalchemy import select
from sqlalchemy.orm import selectinload


def _create(task_id: int) -> int:
    with session_scope() as db:
        task = db.get(DevelopmentTask, task_id)
        assert task is not None
        execution = create_execution(db, task)
        return execution.id


def _snapshot(execution_id: int) -> dict:
    with session_scope() as db:
        execution = db.scalar(
            select(AgentExecution)
            .options(
                selectinload(AgentExecution.file_changes),
                selectinload(AgentExecution.test_executions),
                selectinload(AgentExecution.logs),
                selectinload(AgentExecution.task),
            )
            .where(AgentExecution.id == execution_id)
        )
        assert execution is not None
        return {
            "status": execution.status,
            "stage": execution.current_stage,
            "error": execution.error_message,
            "summary": execution.summary,
            "branch": execution.branch_name,
            "base_branch": execution.base_branch,
            "workspace": execution.workspace_path,
            "plan": execution.plan,
            "plan_approved": execution.plan_approved,
            "validation": execution.validation,
            "changes": [
                {
                    "path": change.file_path,
                    "type": change.change_type,
                    "original": change.original_content,
                    "modified": change.modified_content,
                    "diff": change.diff,
                }
                for change in execution.file_changes
            ],
            "tests": [
                {
                    "command": test.command,
                    "status": test.status,
                    "passed": test.passed_count,
                    "failed": test.failed_count,
                }
                for test in execution.test_executions
            ],
            "corrections": execution.correction_attempts,
            "duration": execution.duration_seconds,
            "completed_at": execution.completed_at,
            "prompt_tokens": execution.prompt_tokens,
            "provider": execution.ai_provider,
            "task_status": execution.task.status if execution.task else None,
            "pr": execution.pull_request,
            "logs": len(execution.logs),
            "files_inspected": execution.files_inspected,
        }


async def _wait_for(execution_id: int, statuses: set[str], timeout_seconds: float = 90) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    snapshot = _snapshot(execution_id)
    while asyncio.get_event_loop().time() < deadline:
        snapshot = _snapshot(execution_id)
        if snapshot["status"] in statuses:
            return snapshot
        await asyncio.sleep(0.1)
    raise AssertionError(f"Execution never reached {statuses}: {snapshot}")


@pytest.mark.asyncio
async def test_demo_execution_runs_real_pipeline(app_env, demo_task):
    execution_id = _create(demo_task["task_id"])
    orchestrator = AgentOrchestrator()
    await orchestrator.run(execution_id)

    snapshot = _snapshot(execution_id)
    assert snapshot["status"] == "completed", snapshot["error"]
    assert snapshot["validation"]["passed"] is True
    assert snapshot["branch"].startswith("autodev/")
    assert snapshot["base_branch"] == "main"
    assert snapshot["corrections"] == 0
    assert snapshot["duration"] is not None and snapshot["duration"] > 0
    assert snapshot["completed_at"] is not None
    assert snapshot["task_status"] == "completed"
    assert snapshot["provider"] == "demo-fixture"
    assert snapshot["prompt_tokens"] == 0
    assert len(snapshot["plan"]["steps"]) >= 4
    assert snapshot["plan_approved"] is True
    assert "calculator/operations.py" in snapshot["files_inspected"]
    assert snapshot["logs"] > 8

    changes = {item["path"]: item for item in snapshot["changes"]}
    assert set(changes) == {"calculator/operations.py", "tests/test_operations.py"}
    assert changes["calculator/operations.py"]["type"] == "modified"
    assert "return a * b" in changes["calculator/operations.py"]["modified"]
    assert "return a + b" in changes["calculator/operations.py"]["original"]
    assert "def test_multiply_positive_numbers" in changes["tests/test_operations.py"]["modified"]
    assert "+def test_multiply_positive_numbers" in changes["tests/test_operations.py"]["diff"]

    assert snapshot["tests"]
    assert all(test["status"] == "passed" for test in snapshot["tests"])
    assert snapshot["tests"][0]["passed"] >= 8

    workspace = Path(snapshot["workspace"])
    assert workspace.is_dir()
    git = GitManager(workspace)
    assert git.current_branch() == snapshot["branch"]
    assert git.has_staged_changes() is False
    assert any("AutoDev:" in line for line in git.log_oneline())

    with session_scope() as db:
        from app.services.execution_service import get_execution_or_404

        detail = build_execution_detail(get_execution_or_404(db, execution_id))
    assert detail.actions.view_diff is True
    assert detail.actions.preview_pull_request is True
    assert detail.actions.create_pull_request is False
    assert detail.actions.retry is True
    assert detail.demo_mode is True
    assert any(step.status == "completed" for step in detail.timeline)


class FlakyProvider(DemoAIProvider):
    """First patch is wrong; the failure-analysis step supplies the fix."""

    def __init__(self) -> None:
        self.failure_calls = 0
        self.change_calls = 0

    async def generate_changes(self, **kwargs):
        self.change_calls += 1
        result = await super().generate_changes(**kwargs)
        payload = json.loads(result.content)
        for edit in payload["edits"]:
            if edit["path"].endswith("calculator/operations.py"):
                edit["content"] = edit["content"].replace("return a * b", "return a - b")
        return AIResult(
            content=json.dumps(payload),
            provider="fake-flaky",
            model="fake",
            usage=AIUsage(prompt_tokens=5, completion_tokens=5),
            fixture=True,
        )

    async def analyze_failure(self, **kwargs):
        self.failure_calls += 1
        context = kwargs["context"]
        ops_path = next(path for path in context.files if path.endswith("calculator/operations.py"))
        source = context.files[ops_path]
        start = source.find("def multiply(")
        end = source.find("\ndef ", start + 1)
        end = end if end != -1 else len(source)
        block = source[start:end]
        fixed = source[:start] + block.replace("return a + b", "return a * b", 1) + source[end:]
        payload = {
            "analysis": "The first patch still returns a difference; use multiplication.",
            "suspected_files": [ops_path],
            "changes": [
                {
                    "path": ops_path,
                    "operation": "update",
                    "content": fixed,
                    "reason": "correct the operator",
                }
            ],
            "manual_suggestions": [],
        }
        return AIResult(
            content=json.dumps(payload),
            provider="fake-flaky",
            model="fake",
            usage=AIUsage(prompt_tokens=7, completion_tokens=3),
            fixture=True,
        )


@pytest.mark.asyncio
async def test_failure_analysis_corrects_a_failing_patch(app_env, demo_task):
    provider = FlakyProvider()
    execution_id = _create(demo_task["task_id"])
    orchestrator = AgentOrchestrator(provider_factory=lambda: provider)
    await orchestrator.run(execution_id)

    snapshot = _snapshot(execution_id)
    assert snapshot["status"] == "completed", snapshot["error"]
    assert provider.change_calls == 1
    assert provider.failure_calls == 1
    assert snapshot["corrections"] == 1
    assert len(snapshot["tests"]) >= 2
    assert snapshot["tests"][-1]["status"] == "passed"
    assert snapshot["tests"][0]["status"] == "failed"
    assert snapshot["prompt_tokens"] == 12
    operations = next(item for item in snapshot["changes"] if item["path"].endswith("operations.py"))
    assert "return a * b" in operations["modified"]
    assert snapshot["validation"]["passed"] is True


class NeverFixProvider(FlakyProvider):
    async def analyze_failure(self, **kwargs):
        self.failure_calls += 1
        context = kwargs["context"]
        ops_path = next(path for path in context.files if path.endswith("calculator/operations.py"))
        source = context.files[ops_path]
        start = source.find("def multiply(")
        end = source.find("\ndef ", start + 1)
        end = end if end != -1 else len(source)
        block = source[start:end]
        still_wrong = source[:start] + block.replace("return a + b", "return a - b", 1) + source[end:]
        payload = {
            "analysis": "Attempted another incorrect operator change.",
            "suspected_files": [ops_path],
            "changes": [
                {
                    "path": ops_path,
                    "operation": "update",
                    "content": still_wrong,
                    "reason": "wrong on purpose",
                }
            ],
            "manual_suggestions": ["Inspect the multiplication logic manually."],
        }
        return AIResult(
            content=json.dumps(payload),
            provider="fake-failing",
            model="fake",
            usage=AIUsage(),
            fixture=True,
        )


@pytest.mark.asyncio
async def test_correction_attempts_are_capped_and_failures_are_not_reported_as_success(app_env, demo_task):
    provider = NeverFixProvider()
    execution_id = _create(demo_task["task_id"])
    await AgentOrchestrator(provider_factory=lambda: provider).run(execution_id)

    snapshot = _snapshot(execution_id)
    assert snapshot["status"] == "failed"
    assert snapshot["task_status"] == "failed"
    assert snapshot["corrections"] == 2
    assert provider.failure_calls == 2
    assert snapshot["error"] is not None and "Tests still fail after 2" in snapshot["error"]
    assert snapshot["validation"] is None
    assert snapshot["pr"] is None
    assert all(test["status"] != "passed" for test in snapshot["tests"])
    assert snapshot["tests"][-1]["failed"] >= 1


@pytest.mark.asyncio
async def test_plan_approval_flow(app_env, demo_task, monkeypatch):
    monkeypatch.setenv("REQUIRE_PLAN_APPROVAL", "true")
    get_settings.cache_clear()

    execution_id = _create(demo_task["task_id"])
    orchestrator = AgentOrchestrator()
    run_task = asyncio.create_task(orchestrator.run(execution_id))
    awaiting = await _wait_for(execution_id, {"awaiting_approval", "failed", "completed"})
    assert awaiting["status"] == "awaiting_approval"
    assert awaiting["stage"] == "awaiting_plan_approval"
    assert awaiting["plan"]["steps"]
    assert awaiting["changes"] == []
    assert awaiting["branch"] is None

    with session_scope() as db:
        from app.services.execution_service import get_execution_or_404

        detail = build_execution_detail(get_execution_or_404(db, execution_id))
    assert detail.actions.approve_plan is True
    assert detail.actions.cancel is True

    assert await orchestrator.approve_plan(execution_id) is True
    await asyncio.wait_for(run_task, timeout=90)
    final = _snapshot(execution_id)
    assert final["status"] == "completed", final["error"]
    assert final["plan_approved"] is True
    assert final["branch"].startswith("autodev/")


@pytest.mark.asyncio
async def test_cancellation_while_waiting_for_approval(app_env, demo_task, monkeypatch):
    monkeypatch.setenv("REQUIRE_PLAN_APPROVAL", "true")
    get_settings.cache_clear()

    execution_id = _create(demo_task["task_id"])
    orchestrator = AgentOrchestrator()
    run_task = asyncio.create_task(orchestrator.run(execution_id))
    await _wait_for(execution_id, {"awaiting_approval", "failed", "completed"})

    assert await orchestrator.cancel(execution_id) is True
    await asyncio.wait_for(run_task, timeout=90)
    snapshot = _snapshot(execution_id)
    assert snapshot["status"] == "cancelled"
    assert snapshot["task_status"] == "cancelled"
    assert snapshot["branch"] is None
    assert snapshot["changes"] == []
    assert snapshot["completed_at"] is not None
