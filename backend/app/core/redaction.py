"""Secret detection and redaction shared by logs, diffs and validation."""

from __future__ import annotations

import re

REDACTED = "***REDACTED***"

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("github_fine_grained", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    (
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]{20,}=*"),
    ),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\b"
            r"\s*[:=]\s*['\"]([A-Za-z0-9_\-./+=]{12,})['\"]"
        ),
    ),
]

# Values that are obviously placeholders and should not block a diff.
_PLACEHOLDER = re.compile(
    r"(?i)(example|sample|dummy|placeholder|changeme|change-me|your[_-]|xxx+|\$\{|<[^>]+>|"
    r"os\.environ|process\.env|getenv|redacted|\*\*\*)"
)


def redact_secrets(text: str) -> str:
    """Replace anything that looks like a credential with a marker."""
    if not text:
        return text
    redacted = text
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def scan_for_secrets(text: str) -> list[dict[str, str]]:
    """Return detected potential secrets with the line they occurred on.

    Placeholder-looking values are ignored to avoid false positives in fixtures,
    documentation and environment examples.
    """
    findings: list[dict[str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            span_text = match.group(0)
            if name == "credential_assignment":
                value = match.group(1)
                if _PLACEHOLDER.search(value):
                    continue
            if _PLACEHOLDER.search(span_text) and name not in {"github_token", "openai_key"}:
                continue
            findings.append(
                {
                    "type": name,
                    "line": str(line_number),
                    "preview": redact_secrets(line.strip())[:160],
                }
            )
    return findings
