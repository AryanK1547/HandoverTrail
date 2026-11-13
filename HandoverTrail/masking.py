from __future__ import annotations

import re


_PATTERNS = (
    ("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    (
        "phone",
        re.compile(
            r"(?<!\d)(?:"
            r"\+91[\s.-]?[6-9]\d{4}[\s.-]?\d{5}|"
            r"0?[6-9]\d{4}[\s.-]?\d{5}|"
            r"\+\d{1,3}(?:[\s().-]?\d){8,14}|"
            r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})"
            r"[\s.-]\d{3,4}[\s.-]\d{4}"
            r")(?!\d)"
        ),
    ),
    (
        "secret",
        re.compile(
            r"(?i)\b(?:AIza[0-9A-Za-z_-]{16,}|sk-[0-9A-Za-z_-]{16,}|"
            r"(?:api[_-]?key|token)\s*[:=]\s*['\"]?[0-9A-Za-z._-]{8,}|"
            r"[A-F0-9]{32,}|[A-Za-z0-9_-]{32,})\b"
        ),
    ),
    (
        "id",
        re.compile(r"(?<!\d)(?:\d[ -]?){8,15}\d(?!\d)"),
    ),
)


def mask_sensitive_text(text: str) -> tuple[str, int]:
    """Replace common contact, credential-like, and long numeric values."""
    masked = text
    count = 0
    for label, pattern in _PATTERNS:
        masked, replacements = pattern.subn(f"[REDACTED:{label}]", masked)
        count += replacements
    return masked, count
