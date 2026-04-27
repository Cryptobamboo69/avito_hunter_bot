from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

AVITO_BASE = "https://www.avito.ru"


def parse_search_results(html: str):
    soup = BeautifulSoup(html or "", "html.parser")

    results: list[dict[str, Any]] = []

    results.extend(parse_html_cards(soup))
    results.extend(parse_json_scripts(soup))

    unique = _dedupe(results)

    logger.info(
        "Avito parser: html_len=%s html_cards=%s total_unique=%s",
        len(html or ""),
        len(results),
        len(unique),
    )

    return unique


def parse_html_cards(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results = []

    selectors = [
        'div[data-marker="item"]',
        '[data-marker^="item"]',
        'div[itemtype*="schema.org/Product"]',
    ]

    cards = []
    for selector in selectors:
        found = soup.select(selector)
        if found:
            cards = found
            break

    for item in cards:
        try:
            title = extract_title(item)
            price = extract_price(item)
            link = extract_link(item)

            if not title or not link:
                continue

            results.append(
                {
                    "title": title,
                    "price": price or "Цена не указана",
                    "link": link,
                    "description": item.get_text(" ", strip=True),
                }
            )
        except Exception:
            logger.exception("Failed to parse Avito HTML card")
            continue

    return results


def extract_title(item) -> str | None:
    candidates = [
        '[data-marker="item-title"]',
        '[itemprop="name"]',
        "h3",
        "a[title]",
    ]

    for selector in candidates:
        tag = item.select_one(selector)
        if tag:
            text = tag.get_text(" ", strip=True)
            if text:
                return clean_text(text)

            title_attr = tag.get("title")
            if title_attr:
                return clean_text(title_attr)

    return None


def extract_price(item) -> str | None:
    candidates = [
        '[data-marker="item-price"]',
        '[itemprop="price"]',
        '[class*="price"]',
    ]

    for selector in candidates:
        tag = item.select_one(selector)
        if tag:
            text = tag.get_text(" ", strip=True)
            if text:
                return clean_text(text)

            content = tag.get("content")
            if content:
                return clean_text(content)

    text = item.get_text(" ", strip=True)
    match = re.search(r"(\d[\d\s]{2,})\s*₽", text)
    if match:
        return clean_text(match.group(0))

    return None


def extract_link(item) -> str | None:
    candidates = [
        'a[data-marker="item-title"]',
        'a[itemprop="url"]',
        'a[href*="/moskva/"]',
        'a[href^="/"]',
    ]

    for selector in candidates:
        tag = item.select_one(selector)
        if tag and tag.get("href"):
            href = tag["href"]
            if href.startswith("http"):
                return href
            return urljoin(AVITO_BASE, href)

    return None


def parse_json_scripts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results = []

    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""

        if not text:
            continue

        if "__initialData__" not in text and "__initial_data__" not in text and "catalog" not in text:
            continue

        json_candidates = extract_json_candidates(text)

        for raw in json_candidates:
            try:
                data = json.loads(raw)
            except Exception:
                continue

            results.extend(extract_items_from_any_json(data))

    return results


def extract_json_candidates(text: str) -> list[str]:
    candidates = []

    patterns = [
        r"window\.__initialData__\s*=\s*(\{.*?\});",
        r"window\.__initial_data__\s*=\s*(\{.*?\});",
        r"__initialData__\s*=\s*(\{.*?\});",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            candidates.append(match.group(1))

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    return candidates


def extract_items_from_any_json(data: Any) -> list[dict[str, Any]]:
    found = []

    def walk(obj: Any):
        if isinstance(obj, dict):
            item = normalize_json_item(obj)
            if item:
                found.append(item)

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    return found


def normalize_json_item(obj: dict[str, Any]) -> dict[str, Any] | None:
    title = (
        obj.get("title")
        or obj.get("name")
        or obj.get("heading")
    )

    url = (
        obj.get("urlPath")
        or obj.get("url")
        or obj.get("uri")
        or obj.get("href")
    )

    if not title or not url:
        return None

    url = str(url)

    if "avito" not in url and not url.startswith("/"):
        return None

    price = extract_json_price(obj)

    return {
        "title": clean_text(title),
        "price": price or "Цена не указана",
        "link": url if url.startswith("http") else urljoin(AVITO_BASE, url),
        "description": clean_text(obj.get("description") or obj.get("text") or title),
    }


def extract_json_price(obj: dict[str, Any]) -> str | None:
    price = obj.get("price")

    if isinstance(price, dict):
        return (
            price.get("string")
            or price.get("formatted")
            or price.get("value")
            or price.get("amount")
        )

    if price:
        return str(price)

    for key in ("priceString", "priceFormatted", "displayPrice"):
        if obj.get(key):
            return str(obj[key])

    return None


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _dedupe(items):
    seen = set()
    unique = []

    for item in items:
        link = item.get("link")
        if not link:
            continue

        if link not in seen:
            seen.add(link)
            unique.append(item)

    return unique