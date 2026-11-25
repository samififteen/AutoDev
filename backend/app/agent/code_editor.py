"""Validated, sandboxed file editing inside the repository workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.agent.models import FileOperation
from app.core.errors import UnsafeOperationError

DENIED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}

DENIED_NAMES = re.compile(
    r"(?i)^(?:\.env(?:\.|$)|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|credentials(?:\.|$)|"
    r"secrets?\.(?:json|ya?ml|toml|txt|ini)|.*\.(?:pem|key|p12|pfx|keystore|jks))$"
)

DENIED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
}

MAX_FILE_BYTES = 500_000


@dataclass(slots=True)
class AppliedEdit:
    path: str
    operation: str
    change_type: str
    original: str | None
    modified: str | None
    reason: str | None = None


class CodeEditor:
    """Applies model-proposed edits after strict path validation.

    All writes are constrained to `root`, paths are canonicalised before use,
    symlinks that escape the workspace are rejected, and the cumulative number
    of touched files is capped.
    """

    def __init__(self, root: Path, *, max_files: int = 10) -> None:
        self.root = root.resolve()
        self.max_files = max_files
        self._originals: dict[str, str | None] = {}
        self._created: set[str] = set()
        self._deleted: set[str] = set()

    def resolve(self, relative_path: str) -> tuple[str, Path]:
        raw = (relative_path or "").strip()
        if not raw:
            raise UnsafeOperationError("An edit was proposed with an empty path")
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise UnsafeOperationError(f"Absolute paths are not allowed: {raw}")
        parts = Path(normalized).parts
        if any(part in {"..", ""} for part in parts):
            raise UnsafeOperationError(f"Path traversal is not allowed: {raw}")
        if any(part in DENIED_DIRS for part in parts):
            raise UnsafeOperationError(f"Edits inside '{raw}' are not allowed")
        name = parts[-1]
        if DENIED_NAMES.match(name):
            raise UnsafeOperationError(f"Refusing to modify a protected file: {raw}")
        if Path(name).suffix.lower() in DENIED_SUFFIXES:
            raise UnsafeOperationError(f"Refusing to modify a binary file: {raw}")

        resolved = (self.root / normalized).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeOperationError(f"Edit escapes the workspace: {raw}") from exc
        if resolved.is_symlink():
            raise UnsafeOperationError(f"Refusing to write through a symlink: {raw}")
        return normalized, resolved

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeOperationError("The target file is not readable UTF-8 text") from exc

    def apply(self, edits: list[FileOperation]) -> list[AppliedEdit]:
        # Validate everything first so a bad edit cannot leave a half-applied set.
        prepared: list[tuple[str, Path, FileOperation]] = []
        prospective: set[str] = set()
        for edit in edits:
            normalized, resolved = self.resolve(edit.path)
            if normalized in prospective:
                raise UnsafeOperationError(f"Duplicate edit for '{normalized}' in one change set")
            prospective.add(normalized)
            if edit.operation in {"create", "update"}:
                if edit.content is None:
                    raise UnsafeOperationError(f"Missing content for '{normalized}'")
                if "\x00" in edit.content:
                    raise UnsafeOperationError(f"Binary content is not allowed: {normalized}")
                if len(edit.content.encode("utf-8")) > MAX_FILE_BYTES:
                    raise UnsafeOperationError(f"File too large to write: {normalized}")
            prepared.append((normalized, resolved, edit))

        touched = set(self._originals) | prospective
        if len(touched) > self.max_files:
            raise UnsafeOperationError(
                f"This change set would touch {len(touched)} files, exceeding the limit of "
                f"{self.max_files}. Narrow the task or raise AGENT_MAX_FILES_MODIFIED."
            )

        applied: list[AppliedEdit] = []
        for normalized, resolved, edit in prepared:
            exists = resolved.is_file()
            if edit.operation == "create":
                if exists and normalized not in self._created:
                    raise UnsafeOperationError(
                        f"Refusing to overwrite existing file '{normalized}' with a create operation"
                    )
            elif edit.operation == "update":
                if not exists and normalized not in self._created:
                    raise UnsafeOperationError(f"Cannot update '{normalized}': the file does not exist")
            elif edit.operation == "delete":
                if not exists:
                    raise UnsafeOperationError(f"Cannot delete '{normalized}': the file does not exist")
                if normalized not in self._originals:
                    self._originals[normalized] = self._read(resolved)
                resolved.unlink()
                self._deleted.add(normalized)
                applied.append(
                    AppliedEdit(
                        path=normalized,
                        operation="delete",
                        change_type="deleted",
                        original=self._originals[normalized],
                        modified=None,
                        reason=edit.reason,
                    )
                )
                continue

            if normalized not in self._originals:
                self._originals[normalized] = self._read(resolved) if exists else None
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(edit.content or "", encoding="utf-8", newline="\n")
            if edit.operation == "create":
                self._created.add(normalized)
                self._deleted.discard(normalized)
            change_type = (
                "added" if normalized in self._created or self._originals[normalized] is None else "modified"
            )
            applied.append(
                AppliedEdit(
                    path=normalized,
                    operation=edit.operation,
                    change_type=change_type,
                    original=self._originals[normalized],
                    modified=edit.content or "",
                    reason=edit.reason,
                )
            )
        return applied

    def original_for(self, path: str) -> str | None:
        return self._originals.get(path)

    def touched_paths(self) -> list[str]:
        return list(self._originals)

    def baseline_files(self) -> dict[str, str | None]:
        return dict(self._originals)
