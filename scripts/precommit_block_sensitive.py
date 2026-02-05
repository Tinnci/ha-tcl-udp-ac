#!/usr/bin/env python3
"""Pre-commit hook to block sensitive data from being committed."""

from __future__ import annotations

import re
import sys
from pathlib import Path

JWT_RE = re.compile(
    r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"
)
ACCESS_TOKEN_RE = re.compile(
    r"\baccess?token\b\s*[:=]\s*['\"]?[^'\"\s]{16,}", re.IGNORECASE
)
JSONL_CAPTURE_RE = re.compile(r"^tcl_\d+\.jsonl$", re.IGNORECASE)


def is_sensitive_text(text: str) -> bool:
    """Return True when text looks like it contains sensitive tokens."""
    return bool(JWT_RE.search(text) or ACCESS_TOKEN_RE.search(text))


def check_file(path: Path) -> str | None:
    """Return a reason string when the file should be blocked."""
    if JSONL_CAPTURE_RE.match(path.name):
        return "capture jsonl file"

    if not path.is_file():
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    if is_sensitive_text(text):
        return "possible access token or JWT"

    return None


def main(argv: list[str]) -> int:
    """Entry point for the pre-commit hook."""
    if len(argv) <= 1:
        return 0

    blocked: list[str] = []
    for file_arg in argv[1:]:
        path = Path(file_arg)
        reason = check_file(path)
        if reason:
            blocked.append(f"{file_arg}: {reason}")

    if blocked:
        sys.stderr.write("Sensitive data detected. Remove or redact before commit:\n")
        for item in blocked:
            sys.stderr.write(f" - {item}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
