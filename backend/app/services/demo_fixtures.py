"""Shipped demo repository used when no AI key / GitHub token is configured.

This is a real, importable Python project with a deliberate bug. It is copied
into a git repository at runtime so that AutoDev's clone/branch/diff/test
pipeline operates on genuine git history and real test output.
"""

from __future__ import annotations

DEMO_OWNER = "autodev-demo"
DEMO_REPO_NAME = "calculator"
DEMO_DESCRIPTION = (
    "Sample calculator package with a deliberately incorrect multiply() implementation. "
    "Used by AutoDev demo mode; all edits and test runs are real."
)

DEMO_ISSUES: list[dict] = [
    {
        "number": 1,
        "title": "Fix the multiplication function and add unit tests",
        "body": (
            "The `multiply` function in calculator/operations.py returns the sum of its "
            "arguments instead of the product. Fix the implementation and add unit tests "
            "covering positive numbers, negative numbers and zero."
        ),
        "labels": ["bug", "tests"],
        "assignees": [],
        "state": "open",
        "demo": True,
    },
    {
        "number": 2,
        "title": "Add a clamp helper and unit tests",
        "body": (
            "Add a `clamp(value, low, high)` helper to calculator/operations.py that limits "
            "value to the inclusive [low, high] range, validate that low <= high, and cover "
            "it with unit tests."
        ),
        "labels": ["enhancement", "tests"],
        "assignees": [],
        "state": "open",
        "demo": True,
    },
]

DEMO_TASKS: list[dict] = [
    {
        "title": DEMO_ISSUES[0]["title"],
        "description": DEMO_ISSUES[0]["body"],
        "priority": "high",
        "github_issue_number": 1,
        "labels": ["bug", "tests"],
        "source": "github_issue",
    },
    {
        "title": DEMO_ISSUES[1]["title"],
        "description": DEMO_ISSUES[1]["body"],
        "priority": "medium",
        "github_issue_number": None,
        "labels": ["enhancement", "tests"],
        "source": "custom",
    },
]
