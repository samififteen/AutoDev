"""Structured data produced by the AI layer and validated before use."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PlanStep(BaseModel):
    index: int = 1
    title: str = Field(min_length=3, max_length=500)
    detail: str | None = Field(default=None, max_length=2000)


class ImplementationPlan(BaseModel):
    summary: str = Field(min_length=3)
    steps: list[PlanStep] = Field(min_length=1)
    files_likely_affected: list[str] = []
    test_plan: list[str] = []
    risks: list[str] = []

    @field_validator("steps")
    @classmethod
    def _renumber(cls, steps: list[PlanStep]) -> list[PlanStep]:
        for index, step in enumerate(steps, start=1):
            step.index = index
        return steps


class FileOperation(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    operation: Literal["create", "update", "delete"]
    content: str | None = None
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return value.strip().replace("\\", "/")

    @field_validator("operation", mode="before")
    @classmethod
    def _normalize_operation(cls, value: object) -> object:
        if isinstance(value, str):
            mapping = {
                "modify": "update",
                "edit": "update",
                "change": "update",
                "add": "create",
                "new": "create",
                "remove": "delete",
            }
            return mapping.get(value.strip().lower(), value.strip().lower())
        return value


class ChangeSet(BaseModel):
    summary: str = ""
    edits: list[FileOperation] = []
    notes: str | None = None


class FailureAnalysis(BaseModel):
    analysis: str
    suspected_files: list[str] = []
    changes: list[FileOperation] = []
    manual_suggestions: list[str] = []


class PRSummary(BaseModel):
    summary: str
    limitations: list[str] = []
    testing_notes: str | None = None
