from __future__ import annotations

import re

PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?i)(?:token|api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?:\bghp_|\bsk-)[A-Za-z0-9_-]{12,}"),
)


def redact_text(value: str) -> str:
    result = value
    for pattern in PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def redact(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        protected = {"token", "api_key", "api-key", "password", "secret", "credential", "credentials"}
        return {key: ("[REDACTED]" if key.lower() in protected else redact(item)) for key, item in value.items()}
    return value
