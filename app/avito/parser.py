from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from app.models import Listing
from app.utils.price import parse_price


def parse_search_results(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    return _from_json_ld(soup)

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

    url = str(url)

    # Только реальные объявления, а не разделы/категории/баннеры
    if not _looks_like_listing_url(url):
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
        url=url,
        price=price,
        location=None,
        description=item.get("description"),
        image_url=image_url,
        raw=item,
    )


for a in soup.find_all("a", href=True):
    href = a["href"]

    if not href:
        continue

    if href.startswith("/"):
        url = "https://www.avito.ru" + href
    elif href.startswith("http"):
        url = href
    else:
        continue

    # ❌ только реальные объявления
    if "/item/" not in url:
        continue

    text = a.get_text(" ", strip=True).lower()

    if not text:
        continue

    # ❌ мусор
    bad_words = [
        "доставка",
        "приложение",
        "подробнее",
        "скидки",
        "путешеств",
        "аренда",
        "отель",
        "квартир",
        "avito",
    ]

    if any(word in text for word in bad_words):
        continue

    # ✅ строго под задачу
    good_words = [
        "nespresso",
        "essenza",
        "c30",
    ]

    if not any(word in text for word in good_words):
        continue

    title = text.strip()
    price = parse_price(text)

    # 💰 фильтр цены
    if price is None or price > 3000:
        continue

    results.append(
        Listing(
            external_id=url,
            title=title,
            url=url,
            price=price,
            location=None,
            description=None,
            image_url=None,
            raw={"href": href, "text": text},
        )
    )

    return _dedupe(results)


def _looks_like_listing_href(href: str) -> bool:
    href = href.lower()

    # Классический паттерн объявления Авито: ..._1234567890
    if re.search(r"_\d{7,}($|\?)", href):
        return True

    # Иногда попадаются такие варианты
    if re.search(r"/item/\d{7,}", href):
        return True

    return False


def _looks_like_listing_url(url: str) -> bool:
    url = url.lower()

    if "avito.ru" not in url:
        return False

    # Отсекаем явный мусор
    if any(x in url for x in [
        "/travel",
        "/apps",
        "/profile",
        "/brands",
        "/favorites",
        "/blocked",
        "/support",
        "/help",
        "/all/",
    ]):
        return False

    if re.search(r"_\d{7,}($|\?)", url):
        return True

    if re.search(r"/item/\d{7,}", url):
        return True

    return False


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