"""Pipeline stage definitions shared by the orchestrator and API."""

from __future__ import annotations

from typing import Final

PIPELINE_STAGES: Final[list[tuple[str, str]]] = [
    ("initializing", "Initializing agent"),
    ("analyzing_repository", "Inspecting repository"),
    ("analyzing_task", "Analyzing task"),
    ("reading_files", "Reading source files"),
    ("planning", "Generating implementation plan"),
    ("awaiting_plan_approval", "Waiting for plan approval"),
    ("creating_branch", "Creating working branch"),
    ("modifying_files", "Modifying files"),
    ("running_tests", "Running tests"),
    ("analyzing_failures", "Analyzing test failures"),
    ("validating_changes", "Reviewing changes"),
    ("awaiting_pull_request", "Preparing pull request"),
]

STAGE_ORDER: Final[dict[str, int]] = {key: index for index, (key, _) in enumerate(PIPELINE_STAGES)}

TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"completed", "failed", "cancelled"})
ACTIVE_STATUSES: Final[frozenset[str]] = frozenset({"queued", "running", "awaiting_approval"})


def stage_index(stage: str | None) -> int:
    return STAGE_ORDER.get(stage or "", -1)


def build_timeline(current_stage: str | None, status: str) -> list[dict[str, str]]:
    """Compute timeline states from persisted backend state only."""
    current_index = stage_index(current_stage)
    timeline: list[dict[str, str]] = []
    for index, (key, label) in enumerate(PIPELINE_STAGES):
        if status in {"failed", "cancelled"}:
            if current_index == -1:
                state = "pending"
            elif index < current_index:
                state = "completed"
            elif index == current_index:
                state = "failed"
            else:
                state = "skipped"
        elif current_index == -1:
            state = "pending"
        elif index < current_index:
            state = "completed"
        elif index == current_index:
            state = "active" if status in ACTIVE_STATUSES else "completed"
        else:
            state = "pending"
        timeline.append({"key": key, "label": label, "status": state})

    if status == "completed" and timeline:
        timeline[-1]["status"] = "completed"
    return timeline
