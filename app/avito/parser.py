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
    results.extend(parse_json_ld(soup))
    results.extend(parse_initial_json(soup))

    unique = _dedupe(results)

    logger.info(
        "Avito parser: html_len=%s total_raw=%s total_unique=%s",
        len(html or ""),
        len(results),
        len(unique),
    )

    return unique


def parse_html_cards(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results = []

    cards = []

    selectors = [
        'div[data-marker="item"]',
        '[data-marker*="item"]',
        'div[itemtype*="schema.org/Product"]',
        'div[class*="iva-item"]',
        'div[class*="styles-module-root"]',
    ]

    for selector in selectors:
        found = soup.select(selector)
        if found:
            cards = found
            break

    for card in cards:
        title = extract_title(card)
        price = extract_price(card)
        link = extract_link(card)
        description = ""
        if not title or not link:
            continue

        if not looks_like_listing_url(link):
            continue

        results.append(
            {
                "title": clean_text(title),
                "price": clean_text(price or "Цена не указана"),
                "link": normalize_url(link),
                "description": clean_text(description),
            }
        )

    return results


def extract_title(card) -> str | None:
    selectors = [
        '[data-marker="item-title"]',
        'a[data-marker="item-title"]',
        '[itemprop="name"]',
        'h3',
        'a[title]',
    ]

    for selector in selectors:
        tag = card.select_one(selector)
        if not tag:
            continue

        text = tag.get_text(" ", strip=True)
        if text:
            return text

        title_attr = tag.get("title")
        if title_attr:
            return title_attr

    return None


def extract_price(card) -> str | None:
    selectors = [
        '[data-marker="item-price"]',
        '[itemprop="price"]',
        '[class*="price"]',
        '[class*="Price"]',
    ]

    for selector in selectors:
        tag = card.select_one(selector)
        if not tag:
            continue

        text = tag.get_text(" ", strip=True)
        if text:
            return text

        content = tag.get("content")
        if content:
            return str(content)

    text = card.get_text(" ", strip=True)
    match = re.search(r"(\d[\d\s]{2,})\s*₽", text)
    if match:
        return match.group(0)

    return None


def extract_link(card) -> str | None:
    selectors = [
        'a[data-marker="item-title"]',
        'a[itemprop="url"]',
        'a[href*="/moskva/"]',
        'a[href*="/rossiya/"]',
        'a[href^="/"]',
    ]

    for selector in selectors:
        tag = card.select_one(selector)
        if tag and tag.get("href"):
            return urljoin(AVITO_BASE, tag["href"])

    return None


def parse_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        results.extend(extract_items_from_json(data))

    return results


def parse_initial_json(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results = []

    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if not text:
            continue

        if not any(key in text for key in ["__initialData__", "__initial_data__", "catalog", "items"]):
            continue

        for raw_json in extract_json_candidates(text):
            try:
                data = json.loads(raw_json)
            except Exception:
                continue

            results.extend(extract_items_from_json(data))

    return results


def extract_json_candidates(text: str) -> list[str]:
    candidates = []

    patterns = [
        r"window\.__initialData__\s*=\s*(\{.*?\});",
        r"window\.__initial_data__\s*=\s*(\{.*?\});",
        r"__initialData__\s*=\s*(\{.*?\});",
        r"__INITIAL_STATE__\s*=\s*(\{.*?\});",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            candidates.append(match.group(1))

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    return candidates


def extract_items_from_json(data: Any) -> list[dict[str, Any]]:
    results = []

    def walk(obj: Any):
        if isinstance(obj, dict):
            item = normalize_json_item(obj)
            if item:
                results.append(item)

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    return results


def normalize_json_item(obj: dict[str, Any]) -> dict[str, Any] | None:
    title = (
        obj.get("title")
        or obj.get("name")
        or obj.get("heading")
        or obj.get("displayTitle")
    )

    url = (
        obj.get("urlPath")
        or obj.get("url")
        or obj.get("uri")
        or obj.get("href")
    )

    if not title or not url:
        return None

    link = normalize_url(str(url))

    if not looks_like_listing_url(link):
        return None

    price = extract_json_price(obj)

    description = (
        obj.get("description")
        or obj.get("text")
        or obj.get("subtitle")
        or title
    )

    return {
        "title": clean_text(title),
        "price": clean_text(price or "Цена не указана"),
        "link": link,
        "description": clean_text(description),
    }


def extract_json_price(obj: dict[str, Any]) -> str | None:
    price = obj.get("price")

    if isinstance(price, dict):
        value = (
            price.get("string")
            or price.get("formatted")
            or price.get("value")
            or price.get("amount")
        )
        return str(value) if value is not None else None

    if price is not None:
        return str(price)

    for key in ["priceString", "priceFormatted", "displayPrice", "formattedPrice"]:
        if obj.get(key):
            return str(obj[key])

    return None


def normalize_url(url: str) -> str:
    if url.startswith("http"):
        return url
    return urljoin(AVITO_BASE, url)


def looks_like_listing_url(url: str) -> bool:
    url_l = url.lower()

    if "avito.ru" not in url_l:
        return False

    bad_parts = [
        "/profile",
        "/favorites",
        "/brands",
        "/items",
        "/search",
        "/help",
        "/apps",
        "/travel",
        "q=",
        "query=",
    ]

    if any(part in url_l for part in bad_parts):
        return False

    if re.search(r"_\d{6,}", url_l):
        return True

    if "/item/" in url_l:
        return True

    return False


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _dedupe(items):
    seen = set()
    unique = []

    for item in items:
        link = item.get("link")
        if not link:
            continue

        if link in seen:
            continue

        seen.add(link)
        unique.append(item)

    return unique