from __future__ import annotations

import json
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
    title = item.get("name") or item.get("title")

    if not url or not title:
        return None

    external_id = str(item.get("sku") or item.get("position") or url)

    offers = item.get("offers") or {}
    price = None
    if isinstance(offers, dict):
        raw_price = offers.get("price")
        if raw_price is not None:
            price = parse_price(str(raw_price))

    image = item.get("image")
    image_url = image if isinstance(image, str) else None

    return Listing(
        external_id=external_id,
        title=str(title),
        url=str(url),
        price=price,
        location=None,
        description=item.get("description"),
        image_url=image_url,
        raw=item,
    )



def _from_links(soup: BeautifulSoup) -> list[Listing]:
    results: list[Listing] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if not href:
            continue

        # 👉 только ссылки с ID (реальные объявления)
        if not re.search(r"/\d{7,}", href):
            continue

        # нормализация ссылки
        if href.startswith("/"):
            url = "https://www.avito.ru" + href
        elif href.startswith("http"):
            url = href
        else:
            continue

        # защита от мусора
        if any(x in url for x in [
            "/travel",
            "/apps",
            "/profile",
            "/brands",
            "/favorites",
            "utm_",
        ]):
            continue

        text = a.get_text(" ", strip=True)

        if not text or len(text) < 10:
            continue

        title = text[:200]
        price = parse_price(text)

        results.append(
            Listing(
                external_id=url,
                title=title,
                url=url,
                price=price,
                location=None,
                description=None,
                image_url=None,
                raw={"href": href},
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