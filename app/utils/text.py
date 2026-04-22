from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).lower().strip()
    value = value.replace("ё", "е")
    value = re.sub(r"\s+", " ", value)
    return value


def contains_any(text: str, patterns: list[str]) -> list[str]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for pattern in patterns:
        p = normalize_text(pattern)
        if p and p in normalized:
            hits.append(pattern)
    return hits
