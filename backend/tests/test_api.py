from __future__ import annotations

import time
from datetime import datetime

import pytest

TERMINAL = {"completed", "failed", "cancelled"}


def wait_for_execution(client, execution_id: int, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/executions/{execution_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.2)
    raise AssertionError(f"Execution did not finish in time: {last}")


def test_health_and_system(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "ok"
    assert data["demo_mode"] is True
    assert data["github_configured"] is False

    info = client.get("/api/system/info").json()
    assert info["ai_provider"] == "demo"
    assert info["limits"]["max_files_modified"] >= 1

    status = client.get("/api/system/status").json()
    assert status["backend"]["status"] == "ok"
    assert status["database"]["status"] == "ok"
    assert status["github"]["status"] == "disabled"
    assert status["ai_provider"]["status"] == "disabled"
    assert status["agent_worker"]["status"] == "ok"


def test_demo_repository_and_issues(client):
    repositories = client.get("/api/repositories").json()
    assert repositories["total"] == 1
    repository = repositories["items"][0]
    assert repository["is_demo"] is True
    assert repository["language"] == "Python"

    issues = client.get(f"/api/repositories/{repository['id']}/issues").json()
    assert len(issues) == 2
    assert issues[0]["number"] == 1
    assert issues[0]["demo"] is True
    assert "multiplication" in issues[0]["title"]

    detail = client.get(f"/api/repositories/{repository['id']}")
    assert detail.status_code == 200
    assert detail.json()["default_branch"] == "main"


def test_task_creation_and_validation(client):
    repository = client.get("/api/repositories").json()["items"][0]

    too_short = client.post("/api/tasks", json={"repository_id": repository["id"], "title": "no"})
    assert too_short.status_code == 422

    missing_repo = client.post(
        "/api/tasks",
        json={"repository_id": 9999, "title": "A valid task title"},
    )
    assert missing_repo.status_code == 404

    response = client.post(
        "/api/tasks",
        json={
            "repository_id": repository["id"],
            "title": "Improve error handling in divide()",
            "description": "Return a clearer error message.",
            "priority": "low",
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert task["source"] == "custom"
    assert task["status"] == "pending"

    listed = client.get(f"/api/tasks?repository_id={repository['id']}&search=error%20handling")
    assert listed.status_code == 200
    assert any(item["id"] == task["id"] for item in listed.json()["items"])


def test_demo_task_execution_end_to_end(client):
    repository = client.get("/api/repositories").json()["items"][0]
    tasks = client.get(f"/api/tasks?repository_id={repository['id']}").json()["items"]
    task = next(item for item in tasks if "multiplication" in item["title"].lower())

    response = client.post(f"/api/tasks/{task['id']}/execute")
    assert response.status_code == 202, response.text
    execution_id = response.json()["id"]

    detail = wait_for_execution(client, execution_id)
    assert detail["status"] == "completed", detail.get("error_message")
    assert detail["branch_name"].startswith("autodev/")
    assert detail["validation"]["passed"] is True
    assert detail["plan"]["steps"]
    assert detail["actions"]["view_diff"] is True
    assert detail["actions"]["create_pull_request"] is False  # demo repo is local
    assert detail["actions"]["preview_pull_request"] is True
    assert any(step["status"] == "completed" for step in detail["timeline"])

    changes = detail["file_changes"]
    assert {change["file_path"] for change in changes} == {
        "calculator/operations.py",
        "tests/test_operations.py",
    }
    operations = next(c for c in changes if c["file_path"] == "calculator/operations.py")
    assert "return a * b" in operations["modified_content"]
    assert "return a + b" in operations["original_content"]

    tests = detail["test_executions"]
    assert tests and all(test["status"] == "passed" for test in tests)
    assert detail["test_executions"][0]["passed_count"] >= 5

    diff = client.get(f"/api/executions/{execution_id}/diff").json()
    assert diff["additions"] > 0
    assert "return a * b" in diff["unified_diff"]

    patch = client.get(f"/api/executions/{execution_id}/diff/patch")
    assert patch.status_code == 200
    assert "return a * b" in patch.text
    assert "attachment" in patch.headers.get("content-disposition", "")

    logs = client.get(f"/api/executions/{execution_id}/logs").json()
    assert logs["total"] > 5
    messages = " ".join(item["message"] for item in logs["items"])
    assert "DEMO MODE" in messages
    assert "Tests passed" in messages

    draft = client.get(f"/api/executions/{execution_id}/pr-draft")
    assert draft.status_code == 200
    assert "Demo fixture" in draft.json()["body"] or "demo fixture" in draft.json()["body"]
    assert draft.json()["branch"] == detail["branch_name"]

    stream = client.get(f"/api/executions/{execution_id}/stream")
    assert stream.status_code == 200
    assert "data:" in stream.text
    assert "Execution completed successfully" in stream.text

    stats = client.get("/api/dashboard/stats").json()
    assert stats["tasks_processed"] >= 1
    assert stats["tasks_completed"] == 1
    assert stats["repositories_connected"] == 1
    assert len(stats["chart"]) == 14
    assert stats["average_duration_seconds"] is not None
    recent = stats["recent_activity"][0]
    assert recent["execution_id"] == execution_id
    assert recent["repository"].startswith("autodev-demo/")

    history = client.get("/api/executions?sort=duration&order=asc").json()
    assert history["total"] >= 1
    assert history["items"][0]["task"]["title"]


def test_execution_conflicts_and_retry(client, demo_task):
    execution = client.post(f"/api/tasks/{demo_task['task_id']}/execute").json()
    execution_id = execution["id"]
    wait_for_execution(client, execution_id)

    approve = client.post(f"/api/executions/{execution_id}/approve-plan")
    assert approve.status_code == 409

    retry_invalid = client.post(f"/api/executions/{execution_id}/retry")
    assert retry_invalid.status_code == 201
    retried = retry_invalid.json()
    assert retried["id"] != execution_id
    finished = wait_for_execution(client, retried["id"])
    assert finished["status"] == "completed"

    history = client.get("/api/executions?search=multiplication").json()
    ids = {item["id"] for item in history["items"]}
    assert {execution_id, retried["id"]}.issubset(ids)

    missing = client.get("/api/executions/999999")
    assert missing.status_code == 404


def test_settings_update_and_secret_masking(client):
    settings = client.get("/api/settings").json()
    assert "api_key" not in settings["ai"]
    assert settings["ai"]["api_key_configured"] is False
    assert settings["testing"]["allowed_commands"]

    agent = dict(settings["agent"])
    agent["max_correction_attempts"] = 1
    agent["max_files_modified"] = 4
    response = client.put("/api/settings", json={"agent": agent})
    assert response.status_code == 200
    updated = response.json()
    assert updated["agent"]["max_correction_attempts"] == 1
    assert updated["agent"]["max_files_modified"] == 4

    invalid = dict(updated["agent"])
    invalid["max_correction_attempts"] = 99
    bad = client.put("/api/settings", json={"agent": invalid})
    assert bad.status_code == 422

    testing = dict(updated["testing"])
    testing["allowed_commands"] = ["python", "bash -i"]
    bad_command = client.put("/api/settings", json={"testing": testing})
    assert bad_command.status_code == 422

    testing["allowed_commands"] = ["python,rm"]
    testing["default_test_command"] = "curl http://example.com"
    bad_default = client.put("/api/settings", json={"testing": testing})
    assert bad_default.status_code == 422


def test_pull_request_endpoints(client):
    listed = client.get("/api/pull-requests").json()
    assert listed["total"] == 0
    missing = client.get("/api/pull-requests/1")
    assert missing.status_code == 404

    docker = client.get("/api/health")
    assert datetime.now().year >= 2024
    assert docker.status_code == 200


@pytest.mark.parametrize("path", ["/api/repositories/999", "/api/tasks/999"])
def test_missing_resources(client, path):
    assert client.get(path).status_code == 404


def test_github_not_configured_is_explicit(client):
    response = client.post("/api/repositories/connect", json={"full_name": "octo/example"})
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "not_configured"
    assert "GITHUB_TOKEN" in payload["error"]["message"]
