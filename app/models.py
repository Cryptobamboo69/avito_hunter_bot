from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SearchTask:
    id: int | None
    name: str
    search_url: str
    max_price: int | None = None
    city: str | None = None
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    brand_filters: list[str] = field(default_factory=list)
    size_filters: list[str] = field(default_factory=list)
    min_score: int = 6
    check_interval_sec: int = 120
    enabled: bool = True


@dataclass(slots=True)
class Listing:
    external_id: str
    title: str
    url: str
    price: int | None
    location: str | None
    description: str | None = None
    seller_name: str | None = None
    image_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text_blob(self) -> str:
        parts = [self.title or "", self.description or "", self.location or "", self.seller_name or ""]
        return " ".join(parts).strip().lower()


@dataclass(slots=True)
class MatchResult:
    matched: bool
    score: int
    reasons: list[str] = field(default_factory=list)
