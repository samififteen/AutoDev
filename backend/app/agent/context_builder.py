"""Task-aware context selection with a strict character budget."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agent.repository_analyzer import FileRecord, RepositoryAnalyzer, RepositoryIndex

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "then",
    "than",
    "have",
    "should",
    "would",
    "could",
    "must",
    "will",
    "need",
    "needs",
    "add",
    "update",
    "fix",
    "make",
    "ensure",
    "existing",
    "code",
    "file",
    "files",
    "function",
    "functions",
    "test",
    "tests",
    "please",
    "user",
    "users",
    "issue",
    "change",
    "changes",
    "using",
    "there",
    "their",
    "them",
    "also",
    "only",
    "some",
    "more",
    "like",
    "does",
    "doesn",
}

LOW_VALUE_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Cargo.lock",
}

MAX_PER_FILE_CHARS = 14_000


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    path_words = re.findall(r"[A-Za-z0-9_]{3,}", text)
    tokens = {word for word in words if word not in STOPWORDS}
    tokens.update(word.lower() for word in path_words if word.lower() not in STOPWORDS)
    return tokens


@dataclass(slots=True)
class RepoContext:
    files: dict[str, str]
    ranking: list[str]
    omitted: list[str]
    char_budget: int

    def render(self) -> str:
        blocks: list[str] = []
        used = 0
        for path, content in self.files.items():
            block = f"### FILE: {path}\n```\n{content}\n```"
            if used + len(block) > self.char_budget and blocks:
                break
            blocks.append(block)
            used += len(block)
        if self.omitted:
            blocks.append(
                "### OMITTED FILES\n"
                + "\n".join(f"- {path}" for path in self.omitted[:40])
                + "\n(Excluded by the context budget; request more context if truly needed.)"
            )
        return "\n\n".join(blocks)

    def get(self, path: str) -> str | None:
        return self.files.get(path)

    def paths(self) -> list[str]:
        return list(self.files)


class ContextBuilder:
    """Ranks files by relevance to the task and enforces a character budget."""

    def __init__(
        self,
        index: RepositoryIndex,
        *,
        max_chars: int = 60_000,
        analyzer: RepositoryAnalyzer | None = None,
    ) -> None:
        self.index = index
        self.max_chars = max(2_000, max_chars)
        self.analyzer = analyzer or RepositoryAnalyzer()

    def _score(self, record: FileRecord, task_tokens: set[str], plan_files: set[str]) -> int:
        if record.path in plan_files:
            return 100
        path_tokens = set(re.split(r"[/_.\-]", record.path.lower()))
        score = 4 * len(task_tokens & path_tokens)
        symbols = {symbol.lower() for symbol in record.symbols}
        score += 3 * len(task_tokens & symbols)
        if record.kind == "test":
            if task_tokens & {"test", "tests", "pytest", "unit", "coverage"}:
                score += 4
        if record.kind == "dependency":
            score += 1
        if record.kind == "docs":
            score -= 2
        if Path_is_readme(record.path):
            score += 3
        if record.path.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
            score += 1
        content = self.analyzer.read_file(self.index.root, record.path, 24_000)
        if content:
            lowered = content.lower()
            matches = sum(1 for token in task_tokens if token in lowered)
            score += min(10, matches)
        return score

    def build(self, task_text: str, plan_files: list[str] | None = None) -> RepoContext:
        task_tokens = _tokens(task_text)
        plan_set = set(plan_files or [])
        candidates: list[tuple[int, FileRecord]] = []
        for record in self.index.files:
            if record.path in LOW_VALUE_FILES or record.kind == "other":
                continue
            if record.size > 400_000:
                continue
            score = self._score(record, task_tokens, plan_set)
            if score <= 0 and record.kind not in {"source", "test"}:
                continue
            candidates.append((score, record))
        candidates.sort(key=lambda item: (-item[0], item[1].path))

        files: dict[str, str] = {}
        ranking: list[str] = []
        omitted: list[str] = []
        used = 0
        for _, record in candidates:
            if used >= self.max_chars:
                omitted.append(record.path)
                continue
            content = self.analyzer.read_file(self.index.root, record.path, MAX_PER_FILE_CHARS)
            if not content:
                omitted.append(record.path)
                continue
            remaining = self.max_chars - used
            if remaining < 400 and files:
                omitted.append(record.path)
                continue
            if len(content) > remaining:
                content = content[: max(200, remaining - 100)] + "\n... [truncated by AutoDev]"
            files[record.path] = content
            ranking.append(record.path)
            used += len(content)
        return RepoContext(files=files, ranking=ranking, omitted=omitted, char_budget=self.max_chars)


def Path_is_readme(path: str) -> bool:
    return path.lower().split("/")[-1].startswith("readme")
