from __future__ import annotations

import logging
from typing import Any

import aiohttp

from app.avito.parser import parse_search_results
from app.avito.search_client import fetch_html

logger = logging.getLogger(__name__)


RESERVE_WORDS = [
    "забронир",
    "зарезерв",
    "бронь",
    "в броне",
    "в резерве",
    "резерв",
]

NESPRESSO_BLOCKED = [
    "капсул",
    "насос",
    "помпа",
    "запчаст",
    "ремонт",
    "корпус",
    "плата",
    "держатель",
    "лоток",
    "контейнер",
    "резервуар",
    "шланг",
    "кнопк",
    "термоблок",
    "аксессуар",
    "подставк",
    "уплотн",
    "прокладк",
    "фильтр",
    "бойлер",
    "разбор",
    "на детали",
    "на запчасти",
    "неисправ",
    "для кофемашин",
    "для nespresso",
]

MARSELL_BLOCKED = [
    "подошва",
    "стельк",
    "шнурк",
    "ремонт",
    "краска",
    "крем",
    "щетка",
    "набойк",
    "запчаст",
    "подметк",
]

SEARCH_PAGE_BLOCKERS = [
    "q=",
    "query=",
    "/search",
    "/all/",
    "/brands/",
    "/favorites",
    "/profile",
    "/items",
    "/rossiya",
    "/moskva?",
    "travel",
    "avito.ru/apps",
]


def normalize_text(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower().strip()


def is_reserved(text: str) -> bool:
    return any(word in text for word in RESERVE_WORDS)


def price_to_int(price_raw: Any) -> int | None:
    if isinstance(price_raw, int):
        return price_raw
    if price_raw is None:
        return None
    digits = "".join(ch for ch in str(price_raw) if ch.isdigit())
    return int(digits) if digits else None


def is_bad_link(link: str) -> bool:
    link_l = link.lower()
    return any(blocker in link_l for blocker in SEARCH_PAGE_BLOCKERS)


def passes_custom_filters(task_name: str, title: str, full_text: str) -> bool:
    task_name_l = task_name.lower()
    text_l = full_text.lower()

    if is_reserved(text_l):
        return False

    if task_name_l == "nespresso_c30":
        has_model = (
            "c30" in text_l
            or "essenza mini" in text_l
            or ("essenza" in text_l and "mini" in text_l)
        )
        if not has_model:
            return False

        if any(word in text_l for word in NESPRESSO_BLOCKED):
            return False

        return True

    if task_name_l == "marsell_shoes":
        if "marsell" not in text_l:
            return False

        has_target = any(
            word in text_l
            for word in [
                "ботин",
                "туфл",
                "лофер",
                "дерби",
                "обув",
            ]
        )
        if not has_target:
            return False

        if "жен" in text_l:
            return False

        if any(word in text_l for word in MARSELL_BLOCKED):
            return False

        return True

    if task_name_l == "marsell_boots":
        if "marsell" not in text_l:
            return False

        if "ботин" not in text_l:
            return False

        if "жен" in text_l:
            return False

        if any(word in text_l for word in MARSELL_BLOCKED):
            return False

        return True

    return True


def extract_item_fields(item: Any) -> tuple[str, str, Any, str]:
    if isinstance(item, dict):
        title = str(item.get("title", "")).strip()
        link = str(item.get("link", "") or item.get("url", "")).strip()
        price_raw = item.get("price")
        description = str(item.get("description", "")).strip()
        return title, link, price_raw, description

    title = str(getattr(item, "title", "")).strip()
    link = str(
        getattr(item, "link", "") or getattr(item, "url", "")
    ).strip()
    price_raw = getattr(item, "price", None)
    description = str(getattr(item, "description", "")).strip()
    return title, link, price_raw, description


def format_result_message(task_name: str, title: str, link: str, price_value: int | None) -> str:
    price_text = f"{price_value} ₽" if price_value is not None else "не указана"
    return (
        f"<b>Новое объявление</b>\n"
        f"Задача: {task_name}\n"
        f"Название: {title}\n"
        f"Цена: {price_text}\n"
        f"Ссылка: {link}"
    )


async def process_task(message, session: aiohttp.ClientSession, task: dict, max_send: int = 5) -> int:
    try:
        html = await fetch_html(session, task["search_url"])
        items = parse_search_results(html)

        if not items:
            await message.answer(f"{task['name']}: ничего не найдено.")
            return 0

        sent = 0
        seen_links: set[str] = set()

        for item in items:
            title, link, price_raw, description = extract_item_fields(item)

            if not title or not link:
                continue

            if is_bad_link(link):
                continue

            if link in seen_links:
                continue
            seen_links.add(link)

            price_value = price_to_int(price_raw)

            if task.get("max_price") is not None and price_value is not None:
                if price_value > int(task["max_price"]):
                    continue

            full_text = normalize_text(title, description)

            if any(x in full_text for x in [
                "объявлен",
                "по запросу",
                "купить товар",
                "товары для",
                "похожие объявления",
            ]):
                continue

            if not passes_custom_filters(task["name"], title, full_text):
                continue

            text = format_result_message(task["name"], title, link, price_value)
            await message.answer(text)
            sent += 1

            if sent >= max_send:
                break

        if sent == 0:
            await message.answer(f"{task['name']}: подходящих объявлений нет.")

        return sent

    except Exception as e:
        logger.exception("Task error")
        await message.answer(f"Ошибка в задаче {task['name']}: {e}")
        return 0