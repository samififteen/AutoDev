"""The AutoDev execution state machine.

Every stage update is persisted before it is published. Tests, branch creation,
diffs and validation are performed against a real isolated git clone.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent.ai import AIProvider, get_ai_provider
from app.agent.ai.base import AIProviderError, parse_pr_summary
from app.agent.code_editor import AppliedEdit, CodeEditor
from app.agent.code_generator import CodeGenerator
from app.agent.context_builder import ContextBuilder
from app.agent.execution_logger import ExecutionLogger, bus
from app.agent.failure_analyzer import FailureAnalyzer
from app.agent.git_manager import GitError, GitManager, authenticated_url
from app.agent.patch_validator import PatchValidator
from app.agent.planning_engine import PlanningEngine
from app.agent.pull_request_manager import build_pull_request_draft
from app.agent.repository_analyzer import RepositoryAnalyzer
from app.agent.test_executor import (
    CommandResult,
    SandboxExecutor,
    TestSuiteResult,
    detect_execution_commands,
)
from app.core.config import get_settings
from app.core.errors import AppError, ConfigurationError, ConflictError, UnsafeOperationError
from app.core.files import remove_tree
from app.core.logging import get_logger
from app.core.redaction import redact_secrets
from app.database.base import utcnow
from app.database.session import session_scope
from app.integrations.github.service import GitHubIntegrationError, GitHubService, get_github_service
from app.models import (
    AgentExecution,
    DevelopmentTask,
    FileChange,
    PullRequest,
    TestExecution,
)
from app.schemas import PullRequestDraft, PullRequestOut
from app.services.settings_service import RuntimeConfig, load_runtime_config
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)

MAX_APPROVAL_WAIT_SECONDS = 900
MAX_STORED_CONTENT = 120_000


class ExecutionCancelled(Exception):
    pass


class ExecutionFailed(Exception):
    def __init__(self, message: str, *, details: Any = None, summary: str | None = None) -> None:
        super().__init__(message)
        self.details = details
        self.summary = summary


@dataclass(slots=True)
class ExecutionContext:
    execution_id: int
    task_id: int
    task_title: str
    task_description: str
    repo_id: int
    repo_owner: str
    repo_name: str
    repo_full_name: str
    repo_clone_url: str | None
    repo_default_branch: str
    repo_is_demo: bool


class AgentOrchestrator:
    def __init__(
        self,
        *,
        provider_factory: Callable[[], AIProvider] | None = None,
        github_factory: Callable[[], GitHubService] | None = None,
    ) -> None:
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._cancel: dict[int, asyncio.Event] = {}
        self._approvals: dict[int, asyncio.Event] = {}
        self._provider_factory = provider_factory or (lambda: get_ai_provider(get_settings()))
        self._github_factory = github_factory or get_github_service

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def active_count(self) -> int:
        return sum(1 for task in self._tasks.values() if not task.done())

    def has_capacity(self, limit: int) -> bool:
        return self.active_count() < limit

    async def start(self, execution_id: int) -> bool:
        runtime = load_runtime_config()
        if not self.has_capacity(runtime.max_concurrent_tasks):
            return False
        self._cancel.setdefault(execution_id, asyncio.Event())
        self._approvals.setdefault(execution_id, asyncio.Event())
        task = asyncio.create_task(self._run_guarded(execution_id), name=f"autodev-execution-{execution_id}")
        self._tasks[execution_id] = task

        def _cleanup(completed: asyncio.Task[None]) -> None:
            self._tasks.pop(execution_id, None)
            with contextlib.suppress(asyncio.CancelledError, Exception):
                completed.exception()

        task.add_done_callback(_cleanup)
        return True

    async def run(self, execution_id: int) -> None:
        self._cancel.setdefault(execution_id, asyncio.Event())
        self._approvals.setdefault(execution_id, asyncio.Event())
        await self._run_guarded(execution_id)

    async def approve_plan(self, execution_id: int) -> bool:
        event = self._approvals.get(execution_id)
        if event is None:
            return False
        event.set()
        return True

    async def cancel(self, execution_id: int) -> bool:
        self._cancel.setdefault(execution_id, asyncio.Event()).set()
        self._approvals.setdefault(execution_id, asyncio.Event()).set()
        return True

    # ------------------------------------------------------------------ #
    # guarded run / terminal states
    # ------------------------------------------------------------------ #
    async def _run_guarded(self, execution_id: int) -> None:
        started = time.monotonic()
        logger_instance = ExecutionLogger(execution_id)
        runtime = load_runtime_config()
        try:
            await asyncio.wait_for(
                self._execute(execution_id, runtime, logger_instance, started),
                timeout=runtime.execution_timeout_seconds + 30,
            )
        except TimeoutError:
            self._mark_failed(
                execution_id,
                logger_instance,
                f"Execution exceeded the {runtime.execution_timeout_seconds}s timeout",
                None,
            )
        except ExecutionCancelled:
            self._mark_cancelled(execution_id, logger_instance)
        except ExecutionFailed as exc:
            self._mark_failed(execution_id, logger_instance, str(exc), exc.details, summary=exc.summary)
        except AppError as exc:
            self._mark_failed(execution_id, logger_instance, exc.message, exc.details)
        except Exception as exc:  # never leave a task in a running state
            details = redact_secrets(traceback.format_exc())[:8000]
            logger_instance.error(f"Unexpected agent failure: {type(exc).__name__}: {exc}")
            self._mark_failed(
                execution_id,
                logger_instance,
                f"Unexpected error: {type(exc).__name__}",
                details,
            )
        finally:
            duration = round(time.monotonic() - started, 2)
            status = "failed"
            with session_scope() as db:
                execution = db.get(AgentExecution, execution_id)
                if execution is not None:
                    if execution.completed_at is None:
                        execution.completed_at = utcnow()
                    execution.duration_seconds = duration
                    status = execution.status
                    if execution.task is not None:
                        execution.task.status = (
                            execution.status
                            if execution.status in {"completed", "failed", "cancelled"}
                            else execution.task.status
                        )
            bus.publish(execution_id, {"type": "end", "status": status})
            self._cancel.pop(execution_id, None)
            self._approvals.pop(execution_id, None)

    def _mark_failed(
        self,
        execution_id: int,
        logger_instance: ExecutionLogger,
        message: str,
        details: Any,
        *,
        summary: str | None = None,
    ) -> None:
        clean_message = redact_secrets(str(message))[:2000]
        clean_details = redact_secrets(str(details))[:8000] if details is not None else None
        logger_instance.error(f"Execution failed: {clean_message}")
        self._update(
            execution_id,
            status="failed",
            error_message=clean_message,
            error_details=clean_details,
            summary=(summary or clean_message)[:4000],
            completed_at=utcnow(),
        )
        stage = self._get_stage(execution_id)
        logger_instance.state("failed", stage)

    def _mark_cancelled(self, execution_id: int, logger_instance: ExecutionLogger) -> None:
        logger_instance.warning("Execution cancelled by user. Workspace and logs were preserved.")
        self._update(
            execution_id,
            status="cancelled",
            summary="Cancelled by the user before completion.",
            completed_at=utcnow(),
        )
        logger_instance.state("cancelled", self._get_stage(execution_id))

    # ------------------------------------------------------------------ #
    # main pipeline
    # ------------------------------------------------------------------ #
    async def _execute(
        self,
        execution_id: int,
        runtime: RuntimeConfig,
        log: ExecutionLogger,
        started: float,
    ) -> None:
        context = self._load_context(execution_id)
        provider = self._provider_factory()
        self._update(
            execution_id,
            status="running",
            current_stage="initializing",
            started_at=utcnow(),
            ai_provider=provider.name,
            ai_model=provider.model,
        )
        log.state("running", "initializing")
        log.info(
            f"Starting AutoDev execution #{execution_id} for '{context.task_title}' "
            f"in {context.repo_full_name}."
        )
        log.info(
            f"AI provider: {provider.name} / {provider.model}. "
            f"Sandbox: {runtime.sandbox_mode}. Max corrections: {runtime.max_correction_attempts}."
        )
        if provider.is_fixture:
            log.warning(
                "DEMO MODE: no AI API key is configured. Plans and edits come from deterministic "
                "fixtures; no model is called and no code should be described as AI-generated. "
                "Branching, file edits, tests and diffs are real."
            )
        try:
            self._check_deadline(started, runtime)
            workspace, git = self._prepare_workspace(context, log)
            base_branch = self._resolve_base_branch(context, git, runtime, log)

            # ---- repository analysis ---------------------------------- #
            self._stage(log, execution_id, "analyzing_repository")
            analyzer = RepositoryAnalyzer()
            index = analyzer.index(workspace)
            summary = index.to_summary()
            log.info(
                f"Indexed {len(index.files)} files ({summary['source_file_count']} source, "
                f"{len(index.test_files)} test). Primary language: "
                f"{summary['primary_language'] or 'unknown'}. Test framework: "
                f"{summary['test_framework'] or 'none detected'}. Purpose: {summary['purpose'][:220]}"
            )

            # ---- task analysis / context ------------------------------ #
            self._stage(log, execution_id, "analyzing_task")
            task_text = f"{context.task_title}\n\n{context.task_description}"
            builder = ContextBuilder(index, max_chars=runtime.ai_max_context_chars)
            initial_context = builder.build(task_text)
            self._update(
                execution_id,
                files_inspected_json=json.dumps(initial_context.ranking),
            )
            log.info(
                f"Selected {len(initial_context.files)} relevant files for the context window "
                f"({sum(len(value) for value in initial_context.files.values())} characters of "
                f"a {runtime.ai_max_context_chars} budget)."
            )
            planning = PlanningEngine(provider)
            analysis_result = await planning.analyze(
                task_title=context.task_title,
                task_description=context.task_description,
                repo_summary=summary,
                context=initial_context,
            )
            self._track_usage(execution_id, provider.name, provider.model, analysis_result)
            log.info("Task analysis complete.")
            self._check_cancel(execution_id)

            # ---- planning --------------------------------------------- #
            self._stage(log, execution_id, "planning")
            plan, plan_result = await planning.create_plan(
                task_title=context.task_title,
                task_description=context.task_description,
                repo_summary=summary,
                context=initial_context,
                analysis=analysis_result.content,
            )
            self._track_usage(execution_id, provider.name, provider.model, plan_result)
            self._update(execution_id, plan_json=json.dumps(plan.model_dump()))
            log.info(f"Implementation plan generated: {plan.summary}")
            for step in plan.steps:
                log.info(f"  {step.index}. {step.title}" + (f" — {step.detail}" if step.detail else ""))
            if plan.risks:
                log.warning("Plan risks: " + "; ".join(plan.risks))

            if runtime.require_plan_approval:
                self._stage(log, execution_id, "awaiting_plan_approval", status="awaiting_approval")
                log.info("Waiting for human approval before any file is modified.")
                await self._wait_for_approval(execution_id, started, runtime)
                self._update(execution_id, plan_approved=True, status="running")
                log.info("Plan approved by the human reviewer.")
            else:
                self._update(execution_id, plan_approved=True)
                log.info("Plan approval is disabled in settings; continuing automatically.")

            self._check_cancel(execution_id)
            self._check_deadline(started, runtime)

            # ---- branch ------------------------------------------------- #
            self._stage(log, execution_id, "creating_branch")
            branch = GitManager.make_branch_name(context.task_title, execution_id)
            try:
                git.create_branch(branch)
            except GitError as exc:
                raise ExecutionFailed(f"Could not create the working branch: {exc}") from exc
            self._update(execution_id, branch_name=branch, base_branch=base_branch)
            log.info(f"Created branch '{branch}' from '{base_branch}'.")

            # ---- code generation -------------------------------------- #
            edit_context = builder.build(task_text, plan.files_likely_affected)
            inspected = list(dict.fromkeys(initial_context.ranking + edit_context.ranking))
            self._update(execution_id, files_inspected_json=json.dumps(inspected))
            self._stage(log, execution_id, "modifying_files")
            generator = CodeGenerator(provider)
            change_set, changes_result = await generator.generate(
                task_title=context.task_title,
                task_description=context.task_description,
                plan=plan.model_dump(),
                repo_summary=summary,
                context=edit_context,
            )
            self._track_usage(execution_id, provider.name, provider.model, changes_result)
            if not change_set.edits:
                raise ExecutionFailed(
                    "The provider returned no file changes; nothing could be verified.",
                    summary="No changes were proposed.",
                )
            log.info(
                f"Proposed {len(change_set.edits)} edit(s): " f"{change_set.summary or 'no summary provided'}"
            )
            if change_set.notes:
                log.info(f"Generator notes: {change_set.notes}")

            editor = CodeEditor(workspace, max_files=runtime.max_files_modified)
            try:
                applied = editor.apply(change_set.edits)
            except UnsafeOperationError as exc:
                raise ExecutionFailed(f"Generated changes were rejected by safety validation: {exc}") from exc
            self._log_applied(log, applied)
            try:
                git.stage_paths([edit.path for edit in applied])
            except GitError as exc:
                raise ExecutionFailed(f"Could not stage generated changes: {exc}") from exc
            self._persist_changes(execution_id, editor, git, workspace)

            # ---- tests ------------------------------------------------ #
            test_commands, check_commands = detect_execution_commands(
                index, default_test_command=runtime.default_test_command
            )
            tests_available = bool(test_commands)
            executor = SandboxExecutor(allowed_commands=runtime.allowed_commands, mode=runtime.sandbox_mode)
            if tests_available:
                suite = await self._execute_tests(
                    execution_id, executor, test_commands, workspace, runtime, 1, log
                )
            else:
                suite = TestSuiteResult(
                    results=[],
                    passed=True,
                    passed_count=0,
                    failed_count=0,
                    failing_tests=[],
                    summary="No test commands detected",
                    output="",
                )
                log.warning(
                    "No automated test command was detected for this repository. Validation will "
                    "record this as a warning; the diff still requires human review."
                )

            correction = 0
            while not suite.passed and correction < runtime.max_correction_attempts:
                correction += 1
                self._update(execution_id, correction_attempts=correction)
                self._stage(log, execution_id, "analyzing_failures")
                log.warning(
                    f"Tests failed. Requesting AI-assisted correction "
                    f"{correction}/{runtime.max_correction_attempts}."
                )
                analysis, failure_result = await FailureAnalyzer(provider).analyze(
                    task_title=context.task_title,
                    test_output=suite.output,
                    failing_tests=suite.failing_tests,
                    plan=plan.model_dump(),
                    context=edit_context,
                    attempt=correction,
                    max_attempts=runtime.max_correction_attempts,
                )
                self._track_usage(execution_id, provider.name, provider.model, failure_result)
                log.info(f"Failure analysis: {analysis.analysis[:800]}")
                for suggestion in analysis.manual_suggestions:
                    log.info(f"Suggested manual check: {suggestion}")
                if not analysis.changes:
                    log.warning("No automated correction was proposed; stopping corrections.")
                    break
                try:
                    fixes = editor.apply(analysis.changes)
                except UnsafeOperationError as exc:
                    log.error(f"Correction rejected by safety validation: {exc}")
                    break
                self._log_applied(log, fixes)
                try:
                    git.stage_paths([edit.path for edit in fixes])
                except GitError as exc:
                    raise ExecutionFailed(f"Could not stage the correction: {exc}") from exc
                self._persist_changes(execution_id, editor, git, workspace)
                suite = await self._execute_tests(
                    execution_id,
                    executor,
                    test_commands,
                    workspace,
                    runtime,
                    correction + 1,
                    log,
                )
            if not suite.passed:
                raise ExecutionFailed(
                    f"Tests still fail after {correction} automatic correction attempt(s).",
                    details=json.dumps(
                        {
                            "summary": suite.summary,
                            "failing_tests": suite.failing_tests,
                            "output_tail": suite.output[-4000:],
                        }
                    ),
                    summary=f"Automated tests failed: {suite.summary}",
                )

            # ---- validation ------------------------------------------- #
            self._stage(log, execution_id, "validating_changes")
            check_results: list[CommandResult] = []
            for command in check_commands:
                log.info(f"Running repository check: {command}")
                result = await executor.run_command(command, workspace, runtime.test_timeout_seconds)
                self._persist_test_result(execution_id, result, attempt=correction + 1)
                check_results.append(result)
                if result.status == "passed":
                    log.info(f"Check passed: {command}")
                else:
                    log.error(f"Check failed: {command}")

            checks_passed = all(result.status == "passed" for result in check_results)
            report = PatchValidator().validate(
                git=git,
                base_branch=base_branch,
                max_files=runtime.max_files_modified,
                expected_paths=set(editor.touched_paths()),
                test_summary=suite.summary,
                test_passed=suite.passed and checks_passed,
                test_output="\n".join(result.output for result in check_results)[-3000:],
            )
            for result in check_results:
                report.add(
                    f"check: {result.command}",
                    result.status == "passed",
                    f"{result.status} (exit {result.exit_code})",
                )
            report.add(
                "tests-detected",
                tests_available,
                "Automated tests were executed"
                if tests_available
                else "No test command was detected; manual review required",
                severity="warning",
            )
            report.finalize()
            self._update(
                execution_id,
                validation_json=json.dumps(report.model_dump()),
                diff_json=json.dumps(
                    {
                        "additions": report.additions,
                        "deletions": report.deletions,
                        "files": [
                            {
                                "path": change.file_path,
                                "additions": change.additions,
                                "deletions": change.deletions,
                                "change_type": change.change_type,
                            }
                            for change in self._current_changes(execution_id)
                        ],
                        "branch": branch,
                        "base_branch": base_branch,
                    }
                ),
            )
            log.info(
                f"Validation {'passed' if report.passed else 'failed'}: {report.summary} "
                f"({report.additions} additions, {report.deletions} deletions)."
            )
            if not report.passed:
                for check in report.checks:
                    if not check.passed and check.severity == "error":
                        log.error(f"Blocking check failed — {check.name}: {check.detail}")
                raise ExecutionFailed(
                    "Change validation failed; no pull request can be created.",
                    details=json.dumps(report.model_dump()),
                    summary=f"Validation failed: {report.summary}",
                )

            # ---- commit & complete ------------------------------------ #
            provider_note = (
                "demo fixture provider — no AI model called"
                if provider.is_fixture
                else "AI-generated changes; human review required"
            )
            message = (
                f"AutoDev: {context.task_title}\n\n"
                f"Execution: #{execution_id}\nBase branch: {base_branch}\n"
                f"Provider: {provider.name} ({provider_note}).\n"
                "Changes were generated in an isolated workspace and validated by the AutoDev pipeline."
            )
            try:
                sha = await asyncio.to_thread(git.commit, message)
            except GitError as exc:
                raise ExecutionFailed(f"Could not commit the validated changes: {exc}") from exc
            log.info(f"Committed validated changes on '{branch}' ({sha[:12]}).")

            summary_text = (
                f"Validation passed with {len(report.files_changed)} changed file(s) "
                f"(+{report.additions}/-{report.deletions}). Tests: {suite.summary}. "
                "A human must approve pull request creation."
            )
            if context.repo_is_demo:
                summary_text += (
                    " This is the local demo repository, so no GitHub pull request can be created; "
                    "connect a GitHub repository for the full workflow."
                )
            self._update(
                execution_id,
                status="completed",
                current_stage="awaiting_pull_request",
                summary=summary_text,
                completed_at=utcnow(),
                error_message=None,
            )
            log.state("completed", "awaiting_pull_request")
            log.info("Execution completed successfully. " + summary_text)
            if provider.is_fixture:
                log.warning(
                    "Reminder: this run used the demo fixture provider. No AI model generated these edits."
                )
        finally:
            with contextlib.suppress(Exception):  # close is best effort
                await provider.aclose()

    # ------------------------------------------------------------------ #
    # pipeline helpers
    # ------------------------------------------------------------------ #
    def _prepare_workspace(self, context: ExecutionContext, log: ExecutionLogger) -> tuple[Path, GitManager]:
        settings = get_settings()
        workspace = settings.workspaces_path / f"execution-{context.execution_id}"
        remove_tree(workspace)
        if not context.repo_clone_url:
            raise ExecutionFailed("The repository has no clone URL; reconnect it first.")
        token = None
        if not context.repo_is_demo:
            try:
                token = self._github_factory().get_auth_token()
            except GitHubIntegrationError as exc:
                raise ExecutionFailed(str(exc)) from exc
        try:
            git = GitManager.clone(context.repo_clone_url, workspace, token=token)
        except GitError as exc:
            raise ExecutionFailed(f"Could not clone the repository: {exc}") from exc
        self._update(context.execution_id, workspace_path=str(workspace))
        log.info(
            f"Cloned {context.repo_full_name} into isolated workspace "
            f"'{workspace.name}' and configured the agent git identity."
        )
        return workspace, git

    def _resolve_base_branch(
        self,
        context: ExecutionContext,
        git: GitManager,
        runtime: RuntimeConfig,
        log: ExecutionLogger,
    ) -> str:
        desired = runtime.default_base_branch or context.repo_default_branch
        current = git.current_branch()
        if desired and desired != current:
            try:
                if git.branch_exists(desired):
                    git.checkout(desired)
                elif git.branch_exists(desired, remote=True):
                    git.checkout_tracking(desired)
                else:
                    log.warning(f"Configured base branch '{desired}' does not exist; using '{current}'.")
                    desired = current
            except GitError as exc:
                log.warning(f"Could not switch to base branch '{desired}': {exc}. Using '{current}'.")
                desired = current
        base = git.current_branch()
        self._update(context.execution_id, base_branch=base)
        log.info(f"Using base branch '{base}'.")
        return base

    async def _execute_tests(
        self,
        execution_id: int,
        executor: SandboxExecutor,
        commands: list[str],
        workspace: Path,
        runtime: RuntimeConfig,
        attempt: int,
        log: ExecutionLogger,
    ) -> TestSuiteResult:
        self._stage(log, execution_id, "running_tests")
        log.info(
            f"Running {len(commands)} test command(s) in the sandbox "
            f"(attempt {attempt}): {', '.join(commands)}"
        )
        suite = await executor.run_commands(
            commands,
            workspace,
            runtime.test_timeout_seconds,
            cancel_check=lambda: self._check_cancel(execution_id),
        )
        self._persist_tests(execution_id, suite, attempt)
        if suite.passed:
            log.info(f"Tests passed: {suite.summary}")
        else:
            log.error(f"Tests failed: {suite.summary}")
            if suite.failing_tests:
                log.error("Failing tests: " + ", ".join(suite.failing_tests[:10]))
        return suite

    def _log_applied(self, log: ExecutionLogger, edits: list[AppliedEdit]) -> None:
        for edit in edits:
            size = len(edit.modified or "")
            log.info(
                f"{edit.change_type.upper()}: {edit.path} ({size} bytes after edit)"
                + (f" — {edit.reason}" if edit.reason else ""),
                stage="modifying_files",
            )

    def _stage(
        self,
        log: ExecutionLogger,
        execution_id: int,
        stage: str,
        *,
        status: str = "running",
    ) -> None:
        self._update(execution_id, current_stage=stage, status=status)
        log.state(status, stage)

    async def _wait_for_approval(self, execution_id: int, started: float, runtime: RuntimeConfig) -> None:
        approval = self._approvals[execution_id]
        cancel = self._cancel[execution_id]
        if approval.is_set():
            return
        remaining = max(1, runtime.execution_timeout_seconds - (time.monotonic() - started))
        wait_for = min(MAX_APPROVAL_WAIT_SECONDS, remaining)
        approval_task = asyncio.create_task(approval.wait())
        cancel_task = asyncio.create_task(cancel.wait())
        try:
            _done, pending = await asyncio.wait(
                {approval_task, cancel_task},
                timeout=wait_for,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in (approval_task, cancel_task):
                if not task.done():
                    task.cancel()
        if cancel.is_set():
            raise ExecutionCancelled()
        if not approval.is_set():
            raise ExecutionFailed("Timed out waiting for human approval of the plan.")

    def _check_cancel(self, execution_id: int) -> None:
        event = self._cancel.get(execution_id)
        if event is not None and event.is_set():
            raise ExecutionCancelled()

    def _check_deadline(self, started: float, runtime: RuntimeConfig) -> None:
        if time.monotonic() - started > runtime.execution_timeout_seconds:
            raise ExecutionFailed(f"Execution exceeded the {runtime.execution_timeout_seconds}s timeout")

    # ------------------------------------------------------------------ #
    # persistence
    # ------------------------------------------------------------------ #
    def _update(self, execution_id: int, **fields: Any) -> None:
        with session_scope() as db:
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                return
            for key, value in fields.items():
                setattr(execution, key, value)

    def _get_stage(self, execution_id: int) -> str:
        with session_scope() as db:
            execution = db.get(AgentExecution, execution_id)
            return execution.current_stage if execution else "failed"

    def _load_context(self, execution_id: int) -> ExecutionContext:
        with session_scope() as db:
            execution = db.scalar(
                select(AgentExecution)
                .options(selectinload(AgentExecution.task).selectinload(DevelopmentTask.repository))
                .where(AgentExecution.id == execution_id)
            )
            if execution is None or execution.task is None or execution.task.repository is None:
                raise ExecutionFailed(f"Execution {execution_id} is missing its task or repository")
            task = execution.task
            repository = task.repository
            return ExecutionContext(
                execution_id=execution_id,
                task_id=task.id,
                task_title=task.title,
                task_description=task.description,
                repo_id=repository.id,
                repo_owner=repository.owner,
                repo_name=repository.name,
                repo_full_name=repository.full_name,
                repo_clone_url=repository.clone_url,
                repo_default_branch=repository.default_branch,
                repo_is_demo=repository.is_demo,
            )

    def _track_usage(self, execution_id: int, provider_name: str, model: str, result) -> None:
        with session_scope() as db:
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                return
            execution.prompt_tokens = (execution.prompt_tokens or 0) + result.usage.prompt_tokens
            execution.completion_tokens = (execution.completion_tokens or 0) + result.usage.completion_tokens
            execution.ai_provider = provider_name
            execution.ai_model = model

    def _persist_changes(
        self,
        execution_id: int,
        editor: CodeEditor,
        git: GitManager,
        workspace: Path,
    ) -> None:
        _additions, _deletions, numstat = git.numstat()
        files_meta: list[dict[str, Any]] = []
        with session_scope() as db:
            db.query(FileChange).filter(FileChange.execution_id == execution_id).delete()
            total_add = total_del = 0
            for path in editor.touched_paths():
                target = workspace / path
                modified: str | None = None
                if target.is_file():
                    try:
                        modified = target.read_text(encoding="utf-8")[:MAX_STORED_CONTENT]
                    except (OSError, UnicodeDecodeError):
                        modified = None
                original = editor.original_for(path)
                original = original[:MAX_STORED_CONTENT] if original else original
                change_type = "deleted" if modified is None else ("added" if original is None else "modified")
                additions, deletions, _binary = numstat.get(path, (0, 0, False))
                total_add += additions
                total_del += deletions
                diff = git.diff_for(path)
                db.add(
                    FileChange(
                        execution_id=execution_id,
                        file_path=path,
                        change_type=change_type,
                        diff=diff[:MAX_STORED_CONTENT],
                        additions=additions,
                        deletions=deletions,
                        original_content=original,
                        modified_content=modified,
                    )
                )
                files_meta.append(
                    {
                        "path": path,
                        "change_type": change_type,
                        "additions": additions,
                        "deletions": deletions,
                    }
                )
            execution = db.get(AgentExecution, execution_id)
            if execution is not None:
                execution.diff_json = json.dumps(
                    {
                        "additions": total_add,
                        "deletions": total_del,
                        "files": files_meta,
                        "branch": execution.branch_name,
                        "base_branch": execution.base_branch,
                    }
                )

    def _persist_tests(self, execution_id: int, suite: TestSuiteResult, attempt: int) -> None:
        for result in suite.results:
            self._persist_test_result(execution_id, result, attempt)

    def _persist_test_result(self, execution_id: int, result: CommandResult, attempt: int) -> None:
        with session_scope() as db:
            db.add(
                TestExecution(
                    execution_id=execution_id,
                    command=result.command,
                    status=result.status,
                    output=result.output,
                    summary=f"{result.passed_count} passed, {result.failed_count} failed",
                    passed_count=result.passed_count,
                    failed_count=result.failed_count,
                    duration_seconds=result.duration_seconds,
                    attempt=attempt,
                )
            )

    def _current_changes(self, execution_id: int) -> list[FileChange]:
        with session_scope() as db:
            return list(
                db.scalars(
                    select(FileChange)
                    .where(FileChange.execution_id == execution_id)
                    .order_by(FileChange.file_path)
                ).all()
            )

    # ------------------------------------------------------------------ #
    # pull requests
    # ------------------------------------------------------------------ #
    async def build_pull_request_draft(
        self,
        execution_id: int,
        *,
        title: str | None = None,
        body: str | None = None,
    ) -> PullRequestDraft:
        with session_scope() as db:
            execution = db.scalar(
                select(AgentExecution)
                .options(
                    selectinload(AgentExecution.task).selectinload(DevelopmentTask.repository),
                    selectinload(AgentExecution.file_changes),
                    selectinload(AgentExecution.test_executions),
                )
                .where(AgentExecution.id == execution_id)
            )
            if execution is None or execution.task is None:
                raise ConflictError(f"Execution {execution_id} is not available")
            validation = execution.validation or {}
            if not validation.get("passed"):
                raise ConflictError("Validation has not passed for this execution")
            task = execution.task
            repository = task.repository
            files = [
                {
                    "file_path": change.file_path,
                    "change_type": change.change_type,
                    "additions": change.additions,
                    "deletions": change.deletions,
                }
                for change in execution.file_changes
            ]
            tests = [
                {
                    "command": test.command,
                    "status": test.status,
                    "passed_count": test.passed_count,
                    "failed_count": test.failed_count,
                }
                for test in execution.test_executions
            ]
            provider_name = execution.ai_provider or "unknown"
            branch = execution.branch_name or ""
            base_branch = execution.base_branch or repository.default_branch
            issue_number = task.github_issue_number
            task_title = task.title

        provider = self._provider_factory()
        summary = None
        provider_note = (
            "demo fixture provider — no AI model called" if provider.is_fixture else f"model {provider.model}"
        )
        try:
            result = await provider.summarize_changes(
                task_title=task_title,
                files=files,
                tests=tests,
                validation=validation,
                provider_note=provider_note,
            )
            try:
                summary = parse_pr_summary(result.content)
            except AIProviderError:
                summary = None
        except AIProviderError:
            summary = None
        finally:
            await provider.aclose()

        return build_pull_request_draft(
            task_title=task_title,
            execution_id=execution_id,
            issue_number=issue_number,
            branch=branch,
            base_branch=base_branch,
            files=files,
            tests=tests,
            validation=validation,
            provider_name=provider_name,
            provider_note=provider_note,
            summary=summary,
            title_override=title,
            body_override=body,
        )

    async def create_pull_request(
        self,
        execution_id: int,
        *,
        title: str | None = None,
        body: str | None = None,
        base_branch: str | None = None,
    ) -> PullRequestOut:
        with session_scope() as db:
            execution = db.scalar(
                select(AgentExecution)
                .options(
                    selectinload(AgentExecution.task).selectinload(DevelopmentTask.repository),
                    selectinload(AgentExecution.pull_request),
                )
                .where(AgentExecution.id == execution_id)
            )
            if execution is None or execution.task is None:
                raise ConflictError(f"Execution {execution_id} is not available")
            if execution.status != "completed":
                raise ConflictError("Only completed executions can create a pull request")
            validation = execution.validation or {}
            if not validation.get("passed"):
                raise ConflictError("Change validation did not pass")
            if execution.pull_request is not None:
                raise ConflictError(
                    f"A pull request already exists for this execution (#{execution.pull_request.number})"
                )
            if not execution.workspace_path or not execution.branch_name:
                raise ConflictError("The execution workspace is missing; re-run the task")
            repository = execution.task.repository
            if repository.is_demo:
                raise ConfigurationError(
                    "The demo repository is local only. Connect a GitHub repository to create a "
                    "real pull request; you can still preview the generated pull request body."
                )
            if not repository.clone_url:
                raise ConfigurationError("The repository has no clone URL")
            workspace = Path(execution.workspace_path)
            branch = execution.branch_name
            target_base = base_branch or execution.base_branch or repository.default_branch
            repo_full_name = repository.full_name
            clone_url = repository.clone_url
            task_title = execution.task.title

        if target_base == branch:
            raise ConflictError("The pull request base branch cannot be the agent branch")
        if not repo_full_name or "/" not in repo_full_name:
            raise ConfigurationError("Repository metadata is incomplete")
        github: GitHubService = self._github_factory()
        if not github.configured:
            raise ConfigurationError(
                "GitHub is not configured. Set GITHUB_TOKEN (or GitHub App credentials) in the "
                "backend environment before creating pull requests."
            )
        if not workspace.is_dir():
            raise ConflictError("The execution workspace no longer exists on disk")

        log = ExecutionLogger(execution_id)
        draft = await self.build_pull_request_draft(execution_id, title=title, body=body)
        git = GitManager(workspace)
        try:
            if git.current_branch() != branch:
                raise ConflictError("The workspace is not on the execution branch")
            if git.has_staged_changes():
                raise ConflictError("The workspace has uncommitted staged changes; re-run validation")
            if not branch.startswith("autodev/"):
                raise ConflictError("Refusing to push a branch outside the autodev/ namespace")
        except GitError as exc:
            raise ConflictError(f"Workspace verification failed: {exc}") from exc

        try:
            token = github.get_auth_token()
            log.info(f"Pushing branch '{branch}' to {repo_full_name} (no force, feature branch only).")
            await asyncio.to_thread(git.push_branch, branch, authenticated_url(clone_url, token))
        except (GitHubIntegrationError, GitError) as exc:
            log.error(f"Branch push failed: {exc}")
            raise AppError(
                f"Could not push the branch to GitHub: {exc}",
                code="github_push_failed",
                status_code=502,
            ) from exc

        try:
            created = await asyncio.to_thread(
                github.create_pull_request,
                repo_full_name,
                head=branch,
                base=target_base,
                title=draft.title,
                body=draft.body,
            )
        except GitHubIntegrationError as exc:
            log.error(f"Pull request creation failed: {exc}")
            raise AppError(str(exc), code="github_error", status_code=502) from exc

        with session_scope() as db:
            row = PullRequest(
                execution_id=execution_id,
                number=created.get("number"),
                title=draft.title,
                body=draft.body,
                url=created.get("url"),
                branch=branch,
                base_branch=target_base,
                status=created.get("state") or "open",
            )
            db.add(row)
            execution = db.get(AgentExecution, execution_id)
            if execution is not None:
                execution.summary = (
                    f"Pull request #{created.get('number')} created for '{task_title}'. "
                    "AutoDev never merges pull requests; human review is required."
                )
            db.flush()
            payload = PullRequestOut.model_validate(row)
        log.info(
            f"Pull request #{created.get('number')} created: {created.get('url')}. "
            "Merging is left to a human reviewer."
        )
        log.state("completed", "awaiting_pull_request")
        return payload


_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None
