"""Application configuration loaded from environment variables and .env files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Runtime settings. Secrets only ever come from the environment."""

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AutoDev"
    environment: str = "development"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_token: str | None = Field(
        default=None, validation_alias=AliasChoices("AUTODEV_API_TOKEN", "API_TOKEN")
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080",
        validation_alias=AliasChoices("CORS_ORIGINS", "AUTODEV_CORS_ORIGINS"),
    )

    database_url: str = Field(
        default="sqlite:///./autodev.db",
        validation_alias=AliasChoices("DATABASE_URL", "AUTODEV_DATABASE_URL"),
    )

    # GitHub
    github_token: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_TOKEN", "AUTODEV_GITHUB_TOKEN")
    )
    github_app_id: str | None = Field(default=None, validation_alias=AliasChoices("GITHUB_APP_ID"))
    github_app_private_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_PRIVATE_KEY")
    )
    github_app_installation_id: str | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_APP_INSTALLATION_ID")
    )
    github_api_url: str = "https://api.github.com"
    github_default_base_branch: str | None = None

    # AI
    ai_provider: Literal["auto", "openai", "demo"] = "auto"
    ai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY")
    )
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_max_context_chars: int = 60_000
    ai_temperature: float = 0.1
    ai_max_tokens: int = 4096

    # Agent
    agent_max_correction_attempts: int = 2
    agent_execution_timeout: int = 600
    agent_test_timeout: int = 180
    agent_max_files_modified: int = 10
    agent_max_concurrent_tasks: int = 2
    require_plan_approval: bool = True
    require_pr_approval: bool = True

    # Sandbox
    sandbox_mode: Literal["local", "docker"] = "local"
    sandbox_url: str = "http://127.0.0.1:8010"
    sandbox_token: str = "local-sandbox-token"  # noqa: S105 - local development default
    allowed_commands: str = "python,python3,pytest,npm,node,yarn,pnpm,ruff,tsc,go,cargo"

    # Paths
    workspace_dir: str = "./data/workspaces"
    demo_repo_dir: str = "./backend/demo_repo"
    frontend_dist_dir: str = "./frontend/dist"

    @field_validator("github_app_private_key", mode="before")
    @classmethod
    def _unescape_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace("\\n", "\n")
        return value

    def _resolve(self, raw: str) -> Path:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def workspaces_path(self) -> Path:
        return self._resolve(self.workspace_dir)

    @property
    def demo_repo_path(self) -> Path:
        return self._resolve(self.demo_repo_dir)

    @property
    def frontend_dist_path(self) -> Path:
        return self._resolve(self.frontend_dist_dir)

    @property
    def demo_mode(self) -> bool:
        """True when no live AI provider is configured."""
        if self.ai_provider == "demo":
            return True
        if self.ai_provider == "auto" and not self.ai_api_key:
            return True
        return False

    @property
    def effective_ai_provider(self) -> str:
        return "demo" if self.demo_mode else "openai"

    @property
    def github_app_configured(self) -> bool:
        return all([self.github_app_id, self.github_app_private_key, self.github_app_installation_id])

    @property
    def github_configured(self) -> bool:
        return bool(self.github_token) or self.github_app_configured

    @property
    def allowed_command_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_commands.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
