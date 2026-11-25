"""Runtime settings: env defaults plus validated database overrides."""

from __future__ import annotations

import json
import re
from typing import Literal

from app.agent.test_executor import CommandPolicy
from app.core.config import get_settings
from app.core.errors import ValidationFailure
from app.core.logging import get_logger
from app.models import AppSetting
from app.schemas import AgentSettings, SettingsOut, SettingsUpdate, TestingSettings
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

logger = get_logger(__name__)

RUNTIME_KEY = "runtime"
PROGRAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")


class RuntimeConfig(BaseModel):
    max_correction_attempts: int = Field(ge=0, le=5)
    execution_timeout_seconds: int = Field(ge=30, le=3600)
    max_files_modified: int = Field(ge=1, le=50)
    max_concurrent_tasks: int = Field(ge=1, le=10)
    require_plan_approval: bool
    require_pr_approval: bool
    default_base_branch: str | None = None
    test_timeout_seconds: int = Field(ge=10, le=1800)
    allowed_commands: list[str]
    default_test_command: str | None = None
    sandbox_mode: Literal["local", "docker"]
    ai_max_context_chars: int = Field(ge=2_000, le=400_000)
    ai_temperature: float = Field(ge=0.0, le=2.0)

    @property
    def command_policy(self) -> CommandPolicy:
        return CommandPolicy(self.allowed_commands)


def env_defaults() -> RuntimeConfig:
    settings = get_settings()
    return RuntimeConfig(
        max_correction_attempts=settings.agent_max_correction_attempts,
        execution_timeout_seconds=settings.agent_execution_timeout,
        max_files_modified=settings.agent_max_files_modified,
        max_concurrent_tasks=settings.agent_max_concurrent_tasks,
        require_plan_approval=settings.require_plan_approval,
        require_pr_approval=settings.require_pr_approval,
        default_base_branch=settings.github_default_base_branch or None,
        test_timeout_seconds=settings.agent_test_timeout,
        allowed_commands=settings.allowed_command_list,
        default_test_command=None,
        sandbox_mode=settings.sandbox_mode,
        ai_max_context_chars=settings.ai_max_context_chars,
        ai_temperature=settings.ai_temperature,
    )


def _merged_payload(base: RuntimeConfig, update: SettingsUpdate) -> dict:
    payload = base.model_dump()
    if update.agent is not None:
        payload.update(update.agent.model_dump())
    if update.testing is not None:
        payload.update(update.testing.model_dump())
    return payload


def _validate_runtime_payload(payload: dict) -> RuntimeConfig:
    commands = payload.get("allowed_commands") or []
    cleaned: list[str] = []
    for command in commands:
        command = str(command).strip()
        if not PROGRAM_RE.match(command):
            raise ValidationFailure(
                f"Allowed command '{command}' is invalid. Use a bare executable name such as 'python'."
            )
        if command not in cleaned:
            cleaned.append(command)
    if not cleaned:
        raise ValidationFailure("At least one allowed command is required")
    payload["allowed_commands"] = cleaned

    branch = payload.get("default_base_branch")
    if branch:
        branch = str(branch).strip()
        if not BRANCH_RE.match(branch) or ".." in branch:
            raise ValidationFailure("Default base branch contains invalid characters")
        payload["default_base_branch"] = branch
    else:
        payload["default_base_branch"] = None

    try:
        config = RuntimeConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailure("Invalid agent settings", details=exc.errors()) from exc

    command = config.default_test_command
    if command:
        try:
            config.command_policy.build_args(command)
        except Exception as exc:
            raise ValidationFailure(f"Default test command is not allowed: {exc}") from exc
    return config


def get_runtime_config(db: Session) -> RuntimeConfig:
    row = db.get(AppSetting, RUNTIME_KEY)
    if row is None:
        return env_defaults()
    try:
        stored = json.loads(row.value)
        payload = {**env_defaults().model_dump(), **stored}
        return _validate_runtime_payload(payload)
    except (ValueError, ValidationError, ValidationFailure) as exc:
        logger.warning("Stored runtime settings are invalid, falling back to env: %s", exc)
        return env_defaults()


def save_runtime_config(db: Session, update: SettingsUpdate) -> RuntimeConfig:
    current = get_runtime_config(db)
    payload = _merged_payload(current, update)
    config = _validate_runtime_payload(payload)
    row = db.get(AppSetting, RUNTIME_KEY)
    serialized = json.dumps(config.model_dump())
    if row is None:
        db.add(AppSetting(key=RUNTIME_KEY, value=serialized))
    else:
        row.value = serialized
    db.commit()
    return config


def load_runtime_config() -> RuntimeConfig:
    from app.database.session import session_scope

    with session_scope() as db:
        return get_runtime_config(db)


def build_agent_settings(config: RuntimeConfig) -> AgentSettings:
    return AgentSettings(
        max_correction_attempts=config.max_correction_attempts,
        execution_timeout_seconds=config.execution_timeout_seconds,
        max_files_modified=config.max_files_modified,
        max_concurrent_tasks=config.max_concurrent_tasks,
        require_plan_approval=config.require_plan_approval,
        require_pr_approval=config.require_pr_approval,
        default_base_branch=config.default_base_branch,
    )


def build_testing_settings(config: RuntimeConfig) -> TestingSettings:
    return TestingSettings(
        test_timeout_seconds=config.test_timeout_seconds,
        allowed_commands=config.allowed_commands,
        default_test_command=config.default_test_command,
        sandbox_mode=config.sandbox_mode,
    )


def get_settings_view(db: Session) -> SettingsOut:
    from app.integrations.github.service import GitHubService

    settings = get_settings()
    runtime = get_runtime_config(db)
    github = GitHubService.from_settings(settings)
    verification = github.verify() if github.configured else None
    return SettingsOut(
        agent=build_agent_settings(runtime),
        testing=build_testing_settings(runtime),
        github={
            "configured": github.configured,
            "auth_mode": github.auth_mode,
            "verified": bool(verification and verification.get("authenticated")) if verification else None,
            "login": verification.get("login") if verification else None,
            "api_url": github.api_url,
            "default_base_branch": runtime.default_base_branch,
            "token_configured": bool(settings.github_token),
            "app_configured": settings.github_app_configured,
            "error": verification.get("error") if verification else None,
        },
        ai={
            "provider": settings.effective_ai_provider,
            "model": "deterministic-fixture" if settings.demo_mode else settings.ai_model,
            "base_url": settings.ai_base_url,
            "api_key_configured": bool(settings.ai_api_key),
            "demo_mode": settings.demo_mode,
            "max_context_chars": runtime.ai_max_context_chars,
            "temperature": runtime.ai_temperature,
        },
    )
