"""GitHub REST integration (PAT or GitHub App) with no token exposure to clients."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redaction import redact_secrets
from github import Auth, Github, GithubException, GithubIntegration

logger = get_logger(__name__)

_verification_cache: dict[str, Any] = {"checked_at": 0.0, "payload": None}
_CACHE_TTL_SECONDS = 60


class GitHubIntegrationError(RuntimeError):
    pass


def _iso(value: Any) -> str | None:
    try:
        return value.isoformat() if value else None
    except AttributeError:
        return None


class GitHubService:
    def __init__(
        self,
        *,
        token: str | None = None,
        app_id: str | None = None,
        private_key: str | None = None,
        installation_id: str | None = None,
        api_url: str = "https://api.github.com",
    ) -> None:
        self._token = token
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self.api_url = api_url.rstrip("/")
        self.app_mode = bool(app_id and private_key and installation_id)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GitHubService:
        settings = settings or get_settings()
        return cls(
            token=settings.github_token,
            app_id=settings.github_app_id,
            private_key=settings.github_app_private_key,
            installation_id=settings.github_app_installation_id,
            api_url=settings.github_api_url,
        )

    @property
    def configured(self) -> bool:
        return bool(self._token or self.app_mode)

    @property
    def auth_mode(self) -> str:
        if self.app_mode:
            return "github_app"
        if self._token:
            return "personal_access_token"
        return "unconfigured"

    # ------------------------------------------------------------------ #
    # authentication
    # ------------------------------------------------------------------ #
    def get_auth_token(self) -> str:
        if self._token:
            return self._token
        if self.app_mode:
            try:
                integration = self._integration()
                authorization = integration.get_access_token(int(self._installation_id or 0))
                return authorization.token
            except Exception as exc:
                raise GitHubIntegrationError(
                    f"Could not obtain a GitHub App installation token: {type(exc).__name__}"
                ) from exc
        raise GitHubIntegrationError("GitHub is not configured")

    def _integration(self) -> GithubIntegration:
        if not (self._app_id and self._private_key):
            raise GitHubIntegrationError("GitHub App credentials are incomplete")
        auth = Auth.AppAuth(int(self._app_id), self._private_key)
        try:
            return GithubIntegration(auth=auth, base_url=self.api_url)
        except TypeError:  # older PyGithub signature
            return GithubIntegration(int(self._app_id), self._private_key, base_url=self.api_url)

    def _client(self) -> Github:
        if not self.configured:
            raise GitHubIntegrationError("GitHub is not configured")
        try:
            return Github(auth=Auth.Token(self.get_auth_token()), base_url=self.api_url, timeout=20)
        except GitHubIntegrationError:
            raise
        except Exception as exc:
            raise GitHubIntegrationError(f"Could not create a GitHub client: {type(exc).__name__}") from exc

    # ------------------------------------------------------------------ #
    # connection
    # ------------------------------------------------------------------ #
    def verify(self, *, force: bool = False) -> dict[str, Any]:
        if not self.configured:
            return {
                "authenticated": False,
                "login": None,
                "mode": self.auth_mode,
                "error": "No GitHub token or App credentials configured",
            }
        cached = _verification_cache["payload"]
        if (
            not force
            and cached is not None
            and time.time() - float(_verification_cache["checked_at"]) < _CACHE_TTL_SECONDS
        ):
            return cached
        try:
            client = self._client()
            user = client.get_user()
            payload = {
                "authenticated": True,
                "login": getattr(user, "login", None),
                "name": getattr(user, "name", None),
                "mode": self.auth_mode,
                "error": None,
            }
        except Exception as exc:
            message = redact_secrets(str(exc))[:300]
            payload = {
                "authenticated": False,
                "login": None,
                "mode": self.auth_mode,
                "error": f"{type(exc).__name__}: {message}" if message else type(exc).__name__,
            }
        _verification_cache["payload"] = payload
        _verification_cache["checked_at"] = time.time()
        return payload

    @staticmethod
    def clear_verification_cache() -> None:
        _verification_cache["payload"] = None
        _verification_cache["checked_at"] = 0.0

    # ------------------------------------------------------------------ #
    # repositories / issues
    # ------------------------------------------------------------------ #
    def list_repositories(self, query: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        try:
            repositories = []
            if self.app_mode:
                integration = self._integration()
                iterator = integration.get_repos(int(self._installation_id or 0))
            else:
                iterator = self._client().get_user().get_repos(sort="updated", direction="desc")
            needle = (query or "").lower().strip()
            for repository in iterator:
                payload = self._repository_payload(repository)
                if (
                    needle
                    and needle
                    not in (
                        f"{payload['owner']}/{payload['name']} {payload['description'] or ''} "
                        f"{payload['language'] or ''}"
                    ).lower()
                ):
                    continue
                repositories.append(payload)
                if len(repositories) >= limit:
                    break
            return repositories
        except GitHubIntegrationError:
            raise
        except GithubException as exc:
            raise GitHubIntegrationError(self._github_error("list repositories", exc)) from exc

    def get_repository(self, full_name: str) -> dict[str, Any]:
        try:
            return self._repository_payload(self._client().get_repo(full_name))
        except GithubException as exc:
            raise GitHubIntegrationError(self._github_error(f"read repository {full_name}", exc)) from exc

    def list_issues(self, full_name: str, *, limit: int = 100, state: str = "open") -> list[dict[str, Any]]:
        try:
            repository = self._client().get_repo(full_name)
            issues = []
            for issue in repository.get_issues(state=state, sort="created", direction="desc"):
                if issue.pull_request is not None:
                    continue
                issues.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "body": (issue.body or "")[:6000],
                        "labels": [label.name for label in issue.labels],
                        "assignees": [assignee.login for assignee in issue.assignees],
                        "state": issue.state,
                        "created_at": _iso(issue.created_at),
                        "html_url": issue.html_url,
                        "demo": False,
                    }
                )
                if len(issues) >= limit:
                    break
            return issues
        except GithubException as exc:
            raise GitHubIntegrationError(self._github_error("list issues", exc)) from exc

    # ------------------------------------------------------------------ #
    # pull requests
    # ------------------------------------------------------------------ #
    def create_pull_request(
        self,
        full_name: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        if head == base:
            raise GitHubIntegrationError("Refusing to open a pull request from the base branch")
        try:
            repository = self._client().get_repo(full_name)
            pull = repository.create_pull(title=title, body=body, head=head, base=base)
            return {
                "number": pull.number,
                "title": pull.title,
                "url": pull.html_url,
                "state": pull.state,
                "branch": head,
                "base_branch": base,
            }
        except GithubException as exc:
            raise GitHubIntegrationError(self._github_error("create pull request", exc)) from exc

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _github_error(self, action: str, exc: GithubException) -> str:
        data = getattr(exc, "data", None) or {}
        message = data.get("message") if isinstance(data, dict) else None
        status = getattr(exc, "status", "?")
        detail = redact_secrets(str(message or exc))[:300]
        return f"GitHub API could not {action} (HTTP {status}): {detail}"

    @staticmethod
    def _repository_payload(repository: Any) -> dict[str, Any]:
        return {
            "github_id": repository.id,
            "owner": repository.owner.login,
            "name": repository.name,
            "description": repository.description,
            "default_branch": repository.default_branch,
            "language": repository.language,
            "visibility": "private" if repository.private else "public",
            "clone_url": repository.clone_url,
            "html_url": repository.html_url,
        }


def get_github_service() -> GitHubService:
    return GitHubService.from_settings()
