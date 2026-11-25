"""Filesystem helpers for workspace lifecycle management."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def remove_tree(path: Path) -> None:
    """Remove a directory tree, clearing read-only bits on Windows git objects."""
    if not path.exists():
        return

    def _onexc(func, target, _exc):  # type: ignore[no-untyped-def]
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            # A locked file is not fatal for workspace cleanup; report via caller logs.
            pass

    if os.name == "nt":
        shutil.rmtree(path, onexc=_onexc)
    else:
        shutil.rmtree(path, ignore_errors=True)
