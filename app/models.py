from future import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    id: int
    name: str
    search_url: str
    min_price: Optional[int]
    max_price: Optional[int]
    keywords: str
    stopwords: str
    brands: str
    sizes: str
    min_score: int
    enabled: bool
    check_interval_sec: int
    last_hash: str
    last_checked_at: Optional[str]
    created_at: str


@dataclass
class Listing:
    url: str
    title: str
    price: Optional[int]
    location: str
    description: str
    image_url: st
