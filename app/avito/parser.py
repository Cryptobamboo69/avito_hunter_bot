from __future__ import annotations

import json
import re
from bs4 import BeautifulSoup
from app.models import Listing
from app.utils.price import parse_price


def parse_search_results(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    listings = _from_json_ld(soup)
    if listings:
        return listings
    return _from_links(soup)


def _from_json_ld(soup: BeautifulSoup) -> list[Listing]:
    results: list[Listing] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text(strip=True)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") in {"ItemList", "CollectionPage"}:
                for el in item.get("itemListElement", []):
                    obj = el.get("item") if isinstance(el, dict) else None
                    if isinstance(obj, dict):
                        listing = _json_ld_item_to_listing(obj)
                        if listing:
                            results.append(listing)
            else:
                listing = _json_ld_item_to_listing(item)
                if listing:
                    results.append(listing)
    return _dedupe(results)


def _json_ld_item_to_listing(item: dict) -> Listing | None:
    url = item.get("url")
    name = item.get("name") or item.get("title")
    if not url or not name:
        return None
    external_id = str(item.get("sku") or item.get("@id") or url)
    offers = item.get("offers") or {}
    price = None
    if isinstance(offers, dict):
        price = parse_price(str(offers.get("price")))
    return Listing(
        external_id=external_id,
        title=name,
        url=url,
        price=price,
        location=None,
        description=item.get("description"),
        image_url=(item.get("image") if isinstance(item.get("image"), str) else None),
        raw=item,
    )


def _from_links(soup):
    results = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/moskva/" not in href:
            continue

        if href.startswith("/"):
            url = "https://www.avito.ru" + href
        else:
            url = href

        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        results.append({
            "url": url,
            "title": title
        })

    return results


def _dedupe(items: list[Listing]) -> list[Listing]:
    result: list[Listing] = []
    seen: set[str] = set()
    for item in items:
        key = item.external_id or item.url
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
