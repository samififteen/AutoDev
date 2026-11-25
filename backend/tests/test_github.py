from __future__ import annotations

from datetime import UTC, datetime

from app.api.deps import get_github
from app.core.config import get_settings
from fastapi.testclient import TestClient


class FakeGitHub:
    configured = True
    auth_mode = "personal_access_token"
    api_url = "https://api.github.com"

    def __init__(self) -> None:
        self.repository = {
            "github_id": 4242,
            "owner": "octo",
            "name": "widget",
            "description": "A widget service",
            "default_branch": "main",
            "language": "Python",
            "visibility": "private",
            "clone_url": "https://github.com/octo/widget.git",
            "html_url": "https://github.com/octo/widget",
        }
        self.issue_calls = 0

    def get_repository(self, full_name: str) -> dict:
        assert full_name == "octo/widget"
        return dict(self.repository)

    def list_issues(self, full_name: str, *, limit: int = 100, state: str = "open") -> list[dict]:
        self.issue_calls += 1
        return [
            {
                "number": 7,
                "title": "Broken endpoint",
                "body": "POST /widget returns 500",
                "labels": ["bug"],
                "assignees": ["octocat"],
                "state": "open",
                "created_at": "2026-01-02T03:04:05+00:00",
                "html_url": "https://github.com/octo/widget/issues/7",
                "demo": False,
            }
        ]

    def get_auth_token(self) -> str:
        return "fake-installation-token"


def test_connect_list_and_issues_with_mocked_github(client):
    fake = FakeGitHub()
    client.app.dependency_overrides[get_github] = lambda: fake

    connected = client.post("/api/repositories/connect", json={"full_name": "octo/widget"})
    assert connected.status_code == 201, connected.text
    repository = connected.json()
    assert repository["owner"] == "octo"
    assert repository["name"] == "widget"
    assert repository["clone_url"] == "https://github.com/octo/widget.git"
    assert repository["visibility"] == "private"
    assert repository["is_demo"] is False

    listed = client.get("/api/repositories?search=widget").json()
    assert listed["total"] >= 1

    issues = client.get(f"/api/repositories/{repository['id']}/issues")
    assert issues.status_code == 200
    assert fake.issue_calls == 1
    payload = issues.json()
    assert payload[0]["number"] == 7
    assert payload[0]["labels"] == ["bug"]
    assert payload[0]["demo"] is False

    refreshed = client.post(f"/api/repositories/{repository['id']}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["html_url"] == "https://github.com/octo/widget"


def test_auth_token_is_enforced_when_configured(app_env, monkeypatch):
    monkeypatch.setenv("AUTODEV_API_TOKEN", "test-secret-token")
    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as secured:
        assert secured.get("/api/health").status_code == 200
        assert secured.get("/api/repositories").status_code == 401
        assert secured.get("/api/repositories", headers={"Authorization": "Bearer wrong"}).status_code == 401
        authorized = secured.get("/api/repositories", headers={"Authorization": "Bearer test-secret-token"})
        assert authorized.status_code == 200
        assert authorized.json()["total"] == 1


def test_ai_secrets_are_never_returned(app_env, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("AI_API_KEY", "sk-live-this-value-must-never-leak")
    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as live_client:
        response = live_client.get("/api/settings")
        assert response.status_code == 200
        body = response.text
        assert "sk-live-this-value-must-never-leak" not in body
        settings = response.json()
        assert settings["ai"]["api_key_configured"] is True
        assert settings["ai"]["demo_mode"] is False
        assert settings["ai"]["provider"] == "openai"

        health = live_client.get("/api/health").json()
        assert health["demo_mode"] is False
        assert health["ai_provider"] == "openai"


def test_github_unconfigured_is_balanced_with_demo_mode(client):
    status = client.get("/api/system/status").json()
    assert status["github"]["status"] == "disabled"

    response = client.post("/api/repositories/connect", json={"full_name": "octo/widget"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "not_configured"


def test_demo_repository_analysis_is_real(client):
    repository = client.get("/api/repositories").json()["items"][0]
    analysis = client.post(f"/api/repositories/{repository['id']}/analyze")
    assert analysis.status_code == 200, analysis.text
    payload = analysis.json()
    summary = payload["summary"]
    assert summary["primary_language"] == "Python"
    assert summary["test_framework"].startswith("pytest")
    assert any("pytest" in command for command in summary["test_commands"])
    assert "calculator/operations.py" in [module["path"] for module in summary["important_modules"]]
    assert payload["repository"]["analysis"]["purpose"]


def test_timestamps_are_utc_serialisable(client):
    repository = client.get("/api/repositories").json()["items"][0]
    created = datetime.fromisoformat(repository["created_at"])
    assert created.year >= 2024
    assert created.tzinfo is None or created.tzinfo.utcoffset(created) == UTC.utcoffset(created)
