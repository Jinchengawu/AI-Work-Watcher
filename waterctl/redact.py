from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("api_key", re.compile(r"\b(?:sk|rk|pk|ghp|github_pat|xox[baprs])-?[A-Za-z0-9_-]{16,}\b")),
    ("credential", re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*([^\s,;]+)")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
)


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    size = len(value)
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def _redact_text(value: str, counts: Counter[str]) -> str:
    result = value
    for kind, pattern in PATTERNS:
        def replacement(match: re.Match[str]) -> str:
            counts[kind] += 1
            if kind == "credential" and match.lastindex:
                return f"{match.group(1)}=[REDACTED]"
            return "[REDACTED]"
        result = pattern.sub(replacement, result)

    def redact_high_entropy(match: re.Match[str]) -> str:
        token = match.group(0)
        if _entropy(token) >= 4.2 and not token.startswith(("http", "rec-", "evt-")):
            counts["high_entropy"] += 1
            return "[REDACTED]"
        return token

    return re.sub(r"\b[A-Za-z0-9_+/=-]{32,}\b", redact_high_entropy, result)


def redact(value: Any) -> tuple[Any, dict[str, int]]:
    counts: Counter[str] = Counter()

    def walk(item: Any) -> Any:
        if isinstance(item, str):
            return _redact_text(item, counts)
        if isinstance(item, list):
            return [walk(part) for part in item]
        if isinstance(item, dict):
            return {key: walk(part) for key, part in item.items()}
        return item

    return walk(value), dict(sorted(counts.items()))
