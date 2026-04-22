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


def _from_links(soup: BeautifulSoup) -> list[Listing]:
    results: list[Listing] = []
    seen_urls: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/item/" in href or re.search(r"/\w+_\d+$", href):
            url = href if href.startswith("http") else f"https://www.avito.ru{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            text = " ".join(link.stripped_strings)
            title = text[:160] if text else "Без названия"
            container_text = " ".join(link.parent.stripped_strings) if link.parent else text
            price = parse_price(container_text)
            external_id_match = re.search(r"_(\d+)(?:\?.*)?$", url)
            external_id = external_id_match.group(1) if external_id_match else url
            results.append(
                Listing(
                    external_id=external_id,
                    title=title,
                    url=url,
                    price=price,
                    location=None,
                    description=container_text[:1000],
                    raw={"source": "fallback_link_parser"},
                )
            )
    return _dedupe(results)


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
