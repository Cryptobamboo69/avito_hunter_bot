from __future__ import annotations

from app.models import Listing, MatchResult, SearchTask
from app.utils.text import contains_any, normalize_text


def match_listing(task: SearchTask, listing: Listing) -> MatchResult:
    score = 0
    reasons: list[str] = []
    blob = normalize_text(listing.text_blob)

    exclude_hits = contains_any(blob, task.exclude_keywords)
    if exclude_hits:
        score -= 8 * len(exclude_hits)
        reasons.append(f"Стоп-слова: {', '.join(exclude_hits)}")

    include_hits = contains_any(blob, task.include_keywords)
    if include_hits:
        score += 3 * len(include_hits)
        reasons.append(f"Ключевые слова: {', '.join(include_hits)}")

    brand_hits = contains_any(blob, task.brand_filters)
    if task.brand_filters and brand_hits:
        score += 2 * len(brand_hits)
        reasons.append(f"Бренд/модель: {', '.join(brand_hits)}")

    size_hits = contains_any(blob, task.size_filters)
    if task.size_filters and size_hits:
        score += 2 * len(size_hits)
        reasons.append(f"Размер/вариант: {', '.join(size_hits)}")
    elif task.size_filters:
        score -= 2
        reasons.append("Нужный размер не найден")

    if task.city and listing.location:
        if normalize_text(task.city) in normalize_text(listing.location):
            score += 2
            reasons.append(f"Город совпал: {listing.location}")
        else:
            score -= 1
            reasons.append(f"Город отличается: {listing.location}")

    if task.max_price is not None:
        if listing.price is None:
            score -= 1
            reasons.append("Цена не распознана")
        elif listing.price <= task.max_price:
            score += 4
            reasons.append(f"Цена ок: {listing.price} ₽ <= {task.max_price} ₽")
        else:
            score -= 4
            reasons.append(f"Цена выше лимита: {listing.price} ₽ > {task.max_price} ₽")

    matched = score >= task.min_score and not exclude_hits
    return MatchResult(matched=matched, score=score, reasons=reasons)
