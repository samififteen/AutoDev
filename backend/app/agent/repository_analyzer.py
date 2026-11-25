"""Repository indexing and static analysis for context building."""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".sql": "SQL",
    ".sh": "Shell",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
}

CODE_LANGUAGES = {
    "Python",
    "TypeScript",
    "JavaScript",
    "Go",
    "Rust",
    "Java",
    "Kotlin",
    "Ruby",
    "PHP",
    "C#",
    "Swift",
}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    "coverage",
    ".coverage",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    "vendor",
    "target",
    ".idea",
    ".vscode",
}

EXCLUDED_FILE_PATTERNS = re.compile(
    r"(?i)^(?:\.env(?:\.|$)|id_(?:rsa|dsa|ecdsa|ed25519)|credentials|secrets?\.|"
    r".*\.(?:pem|key|p12|pfx|keystore|jks|der|pyc|pyo|so|dll|exe|bin|jar|war|zip|tar|gz|"
    r"7z|png|jpe?g|gif|webp|ico|pdf|woff2?|ttf|eot|mp4|mp3|mov|sqlite3?|db))$"
)

DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "Cargo.toml",
    "composer.json",
    "Gemfile",
}

CONFIG_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".eslintrc",
    ".eslintrc.cjs",
    ".eslintrc.json",
    "eslint.config.js",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
    "pytest.ini",
    "tox.ini",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".prettierrc",
    "Makefile",
}

MAX_FILE_BYTES = 200_000
MAX_FILES = 2500
MAX_README_CHARS = 8_000
MAX_DEPENDENCY_CHARS = 20_000


@dataclass(slots=True)
class FileRecord:
    path: str
    size: int
    language: str | None
    kind: str
    symbols: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepositoryIndex:
    root: Path
    files: list[FileRecord]
    readme: str | None
    readme_path: str | None
    dependency_files: dict[str, str]
    git_log: list[str]
    truncated: bool = False

    def paths(self, kind: str | None = None) -> list[str]:
        return [record.path for record in self.files if kind is None or record.kind == kind]

    @property
    def source_files(self) -> list[str]:
        return self.paths("source")

    @property
    def test_files(self) -> list[str]:
        return self.paths("test")

    @property
    def config_files(self) -> list[str]:
        return self.paths("config")

    @property
    def language_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.files:
            if record.language:
                counts[record.language] = counts.get(record.language, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))

    @property
    def primary_language(self) -> str | None:
        for language, _ in self.language_counts.items():
            if language in CODE_LANGUAGES:
                return language
        return None

    def to_summary(self) -> dict[str, Any]:
        test_framework = _detect_test_framework(self)
        test_commands, build_commands, lint_commands = _detect_commands(self)
        dependencies = _detect_dependencies(self)
        modules = sorted(
            (record for record in self.files if record.kind == "source"),
            key=lambda record: len(record.symbols),
            reverse=True,
        )[:12]
        entry_points = _detect_entry_points(self)
        purpose = _extract_purpose(self.readme)
        technologies = _detect_technologies(self, dependencies)
        return {
            "purpose": purpose,
            "primary_language": self.primary_language,
            "technologies": technologies,
            "languages": self.language_counts,
            "entry_points": entry_points,
            "important_modules": [
                {
                    "path": record.path,
                    "language": record.language,
                    "symbols": record.symbols[:15],
                }
                for record in modules
            ],
            "test_framework": test_framework,
            "test_commands": test_commands,
            "build_commands": build_commands,
            "lint_commands": lint_commands,
            "dependencies": dependencies[:60],
            "file_count": len(self.files),
            "source_file_count": len(self.source_files),
            "test_files": self.test_files[:20],
            "config_files": self.config_files[:20],
            "readme_path": self.readme_path,
            "readme_excerpt": (self.readme or "")[:1500],
            "git_log": self.git_log[:10],
            "truncated": self.truncated,
            "generated_at": datetime.now(UTC).isoformat(),
        }


def _is_test_path(path: str) -> bool:
    lower = path.lower()
    name = Path(path).name.lower()
    return (
        "/tests/" in f"/{lower}"
        or lower.startswith("tests/")
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def _classify(path: str) -> str:
    name = Path(path).name
    if _is_test_path(path):
        return "test"
    if name in DEPENDENCY_FILES:
        return "dependency"
    if name in CONFIG_FILES or name.endswith((".yml", ".yaml", ".toml", ".ini", ".cfg")):
        return "config"
    if path.lower().endswith((".md", ".rst", ".txt")) or path.lower().startswith("docs/"):
        return "docs"
    if Path(path).suffix.lower() in {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".cs",
        ".swift",
    }:
        return "source"
    return "other"


def _python_symbols(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            symbols.append(node.name)
    return symbols


_JS_SYMBOL = re.compile(
    r"(?:export\s+(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*))"
    r"|(?:^(?:async\s+)?function\s+([A-Za-z_$][\w$]*))"
    r"|(?:export\s+const\s+([A-Za-z_$][\w$]*))",
    re.MULTILINE,
)


def _js_symbols(source: str) -> list[str]:
    symbols: list[str] = []
    for match in _JS_SYMBOL.finditer(source):
        name = next((group for group in match.groups() if group), None)
        if name and name not in symbols:
            symbols.append(name)
    return symbols[:40]


def _read_text(path: Path, limit: int = MAX_FILE_BYTES) -> str | None:
    try:
        raw = path.read_bytes()[:limit]
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


class RepositoryAnalyzer:
    """Walks a repository and produces a filtered index and summary."""

    def read_file(self, root: Path, relative_path: str, limit: int = MAX_FILE_BYTES) -> str | None:
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        return _read_text(candidate, limit)

    def index(self, root: Path) -> RepositoryIndex:
        root = root.resolve()
        files: list[FileRecord] = []
        readme: str | None = None
        readme_path: str | None = None
        dependency_files: dict[str, str] = {}
        truncated = False

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                name for name in dirnames if name not in EXCLUDED_DIRS and not name.startswith(".git")
            )
            for filename in sorted(filenames):
                if len(files) >= MAX_FILES:
                    truncated = True
                    break
                if EXCLUDED_FILE_PATTERNS.match(filename):
                    continue
                full_path = Path(dirpath) / filename
                if full_path.is_symlink():
                    continue
                try:
                    size = full_path.stat().st_size
                except OSError:
                    continue
                relative = full_path.relative_to(root).as_posix()
                if size > MAX_FILE_BYTES:
                    files.append(
                        FileRecord(relative, size, LANGUAGE_BY_EXT.get(full_path.suffix.lower()), "other")
                    )
                    truncated = True
                    continue
                language = LANGUAGE_BY_EXT.get(full_path.suffix.lower())
                kind = _classify(relative)
                symbols: list[str] = []
                if language == "Python" and kind in {"source", "test"}:
                    source = _read_text(full_path)
                    if source:
                        symbols = _python_symbols(source)
                elif language in {"JavaScript", "TypeScript"} and kind in {"source", "test"}:
                    source = _read_text(full_path)
                    if source:
                        symbols = _js_symbols(source)
                files.append(FileRecord(relative, size, language, kind, symbols))

                if filename in DEPENDENCY_FILES and kind == "dependency":
                    content = _read_text(full_path, MAX_DEPENDENCY_CHARS)
                    if content:
                        dependency_files[relative] = content
                if (
                    readme is None
                    and filename.lower().startswith("readme")
                    and full_path.suffix.lower() in {".md", ".rst", ".txt", ""}
                ):
                    readme = _read_text(full_path, MAX_README_CHARS)
                    readme_path = relative

        git_log = self._read_git_log(root)
        return RepositoryIndex(
            root=root,
            files=files,
            readme=readme,
            readme_path=readme_path,
            dependency_files=dependency_files,
            git_log=git_log,
            truncated=truncated,
        )

    def _read_git_log(self, root: Path) -> list[str]:
        head = root / ".git"
        if not head.exists():
            return []
        import subprocess

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _extract_purpose(readme: str | None) -> str:
    if not readme:
        return "No README found; purpose inferred from source layout."
    lines = [line.strip() for line in readme.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line.startswith(("#", "!", "[", "=", "-", "*", "<")) and not current:
            continue
        current.append(line)
        if len(" ".join(current)) > 400:
            break
    if current:
        paragraphs.append(" ".join(current))
    purpose = next((paragraph for paragraph in paragraphs if len(paragraph) > 30), "")
    return purpose[:700]


def _detect_test_framework(index: RepositoryIndex) -> str | None:
    combined = "\n".join(index.dependency_files.values())
    package = index.dependency_files.get("package.json", "")
    if "pytest" in combined:
        return "pytest"
    if '"vitest"' in package:
        return "vitest"
    if '"jest"' in package:
        return "jest"
    if any(path.endswith(".py") for path in index.test_files):
        return "pytest (inferred)"
    if index.test_files:
        return "unknown"
    return None


def _package_scripts(index: RepositoryIndex) -> dict[str, str]:
    if "package.json" not in index.dependency_files:
        return {}
    try:
        data = json.loads(index.dependency_files["package.json"])
    except json.JSONDecodeError:
        return {}
    scripts = data.get("scripts") or {}
    return {key: value for key, value in scripts.items() if isinstance(value, str)}


def _detect_commands(index: RepositoryIndex) -> tuple[list[str], list[str], list[str]]:
    test_commands: list[str] = []
    build_commands: list[str] = []
    lint_commands: list[str] = []
    scripts = _package_scripts(index)
    python_tests = any(path.endswith(".py") for path in index.test_files)
    has_python = bool(python_tests or any(path.endswith(".py") for path in index.source_files))

    if python_tests or "pytest" in "\n".join(index.dependency_files.values()):
        # Do not force -q: a repository's own addopts may already set it and a
        # doubled -qq suppresses the summary line AutoDev parses for counts.
        test_commands.append("python -m pytest -p no:cacheprovider")
    test_script = scripts.get("test", "")
    if test_script and "no test specified" not in test_script and not test_script.startswith("echo"):
        test_commands.append("npm test --silent")
    if scripts.get("build"):
        build_commands.append("npm run build")
    if scripts.get("lint"):
        lint_commands.append("npm run lint")
    combined_pyproject = index.dependency_files.get("pyproject.toml", "")
    if has_python and ("[tool.ruff" in combined_pyproject or "ruff.toml" in index.config_files):
        lint_commands.append("python -m ruff check .")
    return test_commands, build_commands, lint_commands


def _detect_dependencies(index: RepositoryIndex) -> list[str]:
    dependencies: list[str] = []
    for path, content in index.dependency_files.items():
        name = Path(path).name
        if name.startswith("requirements") and name.endswith(".txt"):
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-", "git+", "http")):
                    continue
                match = re.match(r"([A-Za-z0-9_.\-\[\]]+)", line)
                if match:
                    dependencies.append(match.group(1))
        elif name == "package.json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                continue
            for section in ("dependencies", "devDependencies"):
                dependencies.extend((data.get(section) or {}).keys())
        elif name == "pyproject.toml":
            try:
                import tomllib

                data = tomllib.loads(content)
                project = data.get("project") or {}
                dependencies.extend(_requirement_name(dep) for dep in project.get("dependencies") or [])
                for group in (project.get("optional-dependencies") or {}).values():
                    dependencies.extend(_requirement_name(dep) for dep in group)
                poetry = (data.get("tool") or {}).get("poetry") or {}
                dependencies.extend((poetry.get("dependencies") or {}).keys())
            except Exception as exc:
                logger.debug("Could not parse dependency file %s: %s", path, exc)
                continue
    seen: list[str] = []
    for dependency in dependencies:
        if dependency and dependency not in seen:
            seen.append(dependency)
    return seen


def _requirement_name(requirement: str) -> str:
    return re.split(r"[<>=!~;\[ ]", requirement.strip(), maxsplit=1)[0]


def _detect_technologies(index: RepositoryIndex, dependencies: list[str]) -> list[str]:
    technologies: set[str] = set()
    if index.primary_language:
        technologies.add(index.primary_language)
    dep_lower = {dependency.lower() for dependency in dependencies}
    mapping = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "sqlalchemy": "SQLAlchemy",
        "react": "React",
        "vue": "Vue",
        "svelte": "Svelte",
        "next": "Next.js",
        "vite": "Vite",
        "express": "Express",
        "pytest": "pytest",
        "vitest": "Vitest",
        "jest": "Jest",
        "tailwindcss": "Tailwind CSS",
        "typescript": "TypeScript",
        "pydantic": "Pydantic",
    }
    for dependency, label in mapping.items():
        if dependency in dep_lower:
            technologies.add(label)
    if any(path == "Dockerfile" for path in index.config_files):
        technologies.add("Docker")
    return sorted(technologies)


def _detect_entry_points(index: RepositoryIndex) -> list[str]:
    entries: list[str] = []
    for record in index.files:
        if record.kind != "source":
            continue
        name = Path(record.path).name
        if name in {
            "main.py",
            "app.py",
            "manage.py",
            "server.py",
            "index.ts",
            "index.tsx",
            "main.tsx",
            "main.ts",
        }:
            entries.append(record.path)
    for record in index.files:
        if record.kind == "source" and "app" in record.symbols and record.path.endswith(".py"):
            entries.append(record.path)
    return list(dict.fromkeys(entries))[:10]
