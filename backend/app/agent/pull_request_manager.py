"""Builds reviewer-facing pull request titles and bodies from real results."""

from __future__ import annotations

from typing import Any

from app.agent.models import PRSummary
from app.schemas import PullRequestDraft


def _clean_title(title: str, limit: int = 120) -> str:
    collapsed = " ".join(title.replace("\r", " ").replace("\n", " ").split())
    return collapsed[:limit].rstrip() or "AutoDev changes"


def build_pull_request_draft(
    *,
    task_title: str,
    execution_id: int,
    issue_number: int | None,
    branch: str,
    base_branch: str,
    files: list[dict[str, Any]],
    tests: list[dict[str, Any]],
    validation: dict[str, Any],
    provider_name: str,
    provider_note: str,
    summary: PRSummary | None,
    title_override: str | None = None,
    body_override: str | None = None,
) -> PullRequestDraft:
    title = _clean_title(title_override or f"AutoDev: {task_title}")
    if body_override:
        body = body_override
    else:
        file_lines = (
            "\n".join(
                f"- `{item['file_path']}` — {item['change_type']} (+{item['additions']}/-{item['deletions']})"
                for item in files
            )
            or "- (no files)"
        )
        test_lines = (
            "\n".join(
                f"| `{item['command']}` | {item['status']} | {item.get('passed_count', 0)} | "
                f"{item.get('failed_count', 0)} |"
                for item in tests
            )
            or "| — | not executed | 0 | 0 |"
        )
        checks = validation.get("checks") or []
        check_lines = (
            "\n".join(
                f"- {'x' if check.get('passed') else ' '} {check.get('name')}: {check.get('detail')}"
                for check in checks
            )
            or "- No validation details recorded"
        )
        limitations = "\n".join(f"- {item}" for item in (summary.limitations if summary else []))
        if not limitations:
            limitations = "- Automated changes require human review before merging."
        summary_text = summary.summary if summary else f"Automated change set for: {task_title}"
        testing_notes = summary.testing_notes if summary and summary.testing_notes else "See test table."
        body = f"""## Summary

{summary_text}

## Problem

{task_title}
{("Closes #" + str(issue_number)) if issue_number else ""}

## Changes

{file_lines}

## Tests

| Command | Status | Passed | Failed |
| --- | --- | --- | --- |
{test_lines}

{testing_notes}

## Validation

{check_lines}

## Agent metadata

- Execution: `#{execution_id}`
- Branch: `{branch}` → `{base_branch}`
- AI provider: **{provider_name}** ({provider_note})
- Created by AutoDev. This pull request was not merged or approved automatically.

## Known limitations

{limitations}
"""
    return PullRequestDraft(
        title=title,
        body=body,
        branch=branch,
        base_branch=base_branch,
        provider=provider_name,
        demo_mode="demo" in provider_name.lower(),
    )
