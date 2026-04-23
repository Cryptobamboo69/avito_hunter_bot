from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from html import escape
from typing import Any

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "data/bot.db").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("avito_hunter_bot")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


@dataclass
class Listing:
    key: str
    title: str
    url: str
    price: int | None


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                search_url TEXT NOT NULL,
                max_price INTEGER,
                check_interval_sec INTEGER NOT NULL DEFAULT 30
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items (
                task_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                PRIMARY KEY (task_id, item_key)
            )
            """
        )
        conn.commit()


def add_task(chat_id: int, name: str, search_url: str, max_price: int | None, interval: int) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (chat_id, name, search_url, max_price, check_interval_sec)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, name, search_url, max_price, interval),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_tasks(chat_id: int) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT id, name, search_url, max_price, check_interval_sec
            FROM tasks
            WHERE chat_id = ?
            ORDER BY id
            """,
            (chat_id,),
        ).fetchall()


def all_tasks() -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT id, chat_id, name, search_url, max_price, check_interval_sec
            FROM tasks
            ORDER BY id
            """
        ).fetchall()


def delete_task(chat_id: int, task_id: int) -> bool:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND chat_id = ?",
            (task_id, chat_id),
        )
        conn.execute("DELETE FROM seen_items WHERE task_id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0


def is_seen(task_id: int, item_key: str) -> bool:
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_items WHERE task_id = ? AND item_key = ?",
            (task_id, item_key),
        ).fetchone()
        return row is not None


def mark_seen(task_id: int, item_key: str) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_items (task_id, item_key) VALUES (?, ?)",
            (task_id, item_key),
        )
        conn.commit()


def extract_price(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def dedupe(items: list[Listing]) -> list[Listing]:
    out: list[Listing] = []
    seen: set[str] = set()
    for item in items:
        if item.key in seen:
            continue
        seen.add(item.key)
        out.append(item)
    return out


def parse_json_ld(soup: BeautifulSoup) -> list[Listing]:
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

            item_type = item.get("@type")
            if item_type in {"ItemList", "CollectionPage"}:
                for el in item.get("itemListElement", []):
                    obj = el.get("item") if isinstance(el, dict) else None
                    if not isinstance(obj, dict):
                        continue
                    listing = json_item_to_listing(obj)
                    if listing:
                        results.append(listing)
            else:
                listing = json_item_to_listing(item)
                if listing:
                    results.append(listing)

    return dedupe(results)


def json_item_to_listing(item: dict[str, Any]) -> Listing | None:
    url = item.get("url")
    title = item.get("name") or item.get("title")
    if not url or not title:
        return None

    offers = item.get("offers") or {}
    price: int | None = None
    if isinstance(offers, dict):
        raw_price = offers.get("price")
        if raw_price is not None:
            price = extract_price(str(raw_price))

    key = str(item.get("sku") or item.get("position") or url)
    return Listing(key=key, title=str(title), url=str(url), price=price)


def parse_links(soup: BeautifulSoup) -> list[Listing]:
    results: list[Listing] = []

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

        if "avito.ru" not in url:
            continue

        # отсекаем откровенный мусор
        if any(x in url for x in ["/brands/", "/favorites", "/profile", "/items", "/search"]):
            continue

        text = a.get_text(" ", strip=True)
        if not text:
            continue

        title = text.strip()
        if len(title) < 5:
            continue

        price = extract_price(text)
        results.append(Listing(key=url, title=title[:300], url=url, price=price))

    return dedupe(results)


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=25)) as resp:
        resp.raise_for_status()
        return await resp.text()


async def parse_search_results(session: aiohttp.ClientSession, url: str) -> list[Listing]:
    html = await fetch_html(session, url)
    soup = BeautifulSoup(html, "lxml")

    items = parse_json_ld(soup)
    if items:
        return items

    return parse_links(soup)


def format_listing(task_name: str, item: Listing) -> str:
    price_text = f"{item.price} ₽" if item.price is not None else "цена не найдена"
    return (
        f"🔥 <b>Новое объявление</b>\n"
        f"<b>Задача:</b> {escape(task_name)}\n"
        f"<b>Название:</b> {escape(item.title)}\n"
        f"<b>Цена:</b> {escape(price_text)}\n"
        f"<b>Ссылка:</b> {escape(item.url)}"
    )


async def process_task(
    bot: Bot,
    session: aiohttp.ClientSession,
    task: sqlite3.Row,
    silent_seed: bool = False,
) -> None:
    task_id = int(task["id"])
    chat_id = int(task["chat_id"])
    task_name = str(task["name"])
    search_url = str(task["search_url"])
    max_price = task["max_price"]

    try:
        items = await parse_search_results(session, search_url)
        logger.info("Task %s parsed %d items", task_id, len(items))
    except Exception as e:
        logger.exception("Task %s parse failed: %s", task_id, e)
        return

    new_count = 0

    for item in items:
        if max_price is not None and item.price is not None and item.price > int(max_price):
            continue

        if is_seen(task_id, item.key):
            continue

        mark_seen(task_id, item.key)
        new_count += 1

        if silent_seed:
            continue

        try:
            await bot.send_message(
                chat_id,
                format_listing(task_name, item),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except Exception as e:
            logger.exception("Send failed for task %s: %s", task_id, e)

    logger.info("Task %s new items: %d", task_id, new_count)


async def scheduled_check(bot: Bot) -> None:
    tasks = all_tasks()
    logger.info("Scheduled check: %d tasks", len(tasks))
    if not tasks:
        return

    async with aiohttp.ClientSession() as session:
        for task in tasks:
            await process_task(bot, session, task, silent_seed=False)


HELP_TEXT = (
    "/add_json — добавить задачу JSON-ом\n"
    "/list — список задач\n"
    "/checkall — проверить все задачи\n"
    "/delete <id> — удалить задачу"
)

waiting_json_users: set[int] = set()
scheduler = AsyncIOScheduler()


def parse_task_json(text: str) -> dict[str, Any]:
    data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError("JSON должен быть объектом")

    name = str(data.get("name", "")).strip()
    search_url = str(data.get("search_url", "")).strip()
    max_price_raw = data.get("max_price")
    interval_raw = data.get("check_interval_sec", 30)

    if not name:
        raise ValueError("Поле name пустое")
    if not search_url:
        raise ValueError("Поле search_url пустое")

    max_price = int(max_price_raw) if max_price_raw is not None else None
    interval = int(interval_raw)

    if interval <= 0:
        raise ValueError("check_interval_sec должен быть > 0")

    return {
        "name": name,
        "search_url": search_url,
        "max_price": max_price,
        "check_interval_sec": interval,
    }


async def cmd_start(message: Message) -> None:
    await message.answer("Бот запущен. Используй /help")


async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


async def cmd_add_json(message: Message) -> None:
    waiting_json_users.add(message.chat.id)
    await message.answer(
        "Пришли JSON следующим сообщением.\n\n"
        'Пример:\n'
        '{"name":"nespresso","search_url":"https://www.avito.ru/moskva?q=nespresso&priceMax=3000","max_price":3000,"check_interval_sec":30}'
    )


async def cmd_list(message: Message) -> None:
    tasks = list_tasks(message.chat.id)
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    parts: list[str] = []
    for row in tasks:
        parts.append(
            f"ID {row['id']} | {escape(str(row['name']))}\n"
            f"URL: {escape(str(row['search_url']))}\n"
            f"max_price={row['max_price']} | every={row['check_interval_sec']}s"
        )

    await message.answer("\n\n".join(parts), parse_mode=ParseMode.HTML)


async def cmd_delete(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Используй: /delete <id>")
        return

    try:
        task_id = int(command.args.strip())
    except ValueError:
        await message.answer("ID должен быть числом")
        return

    ok = delete_task(message.chat.id, task_id)
    await message.answer("Удалено." if ok else "Не найдено.")


async def cmd_checkall(message: Message) -> None:
    tasks = list_tasks(message.chat.id)
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    await message.answer(f"Проверяем {len(tasks)} задач...")

    async with aiohttp.ClientSession() as session:
        for task in tasks:
            await process_task(message.bot, session, task, silent_seed=False)


async def catch_json(message: Message) -> None:
    if message.chat.id not in waiting_json_users:
        return

    try:
        data = parse_task_json(message.text or "")
        task_id = add_task(
            chat_id=message.chat.id,
            name=data["name"],
            search_url=data["search_url"],
            max_price=data["max_price"],
            interval=data["check_interval_sec"],
        )
        waiting_json_users.discard(message.chat.id)

        await message.answer(f"Задача добавлена. ID: {task_id}")

        task = next((t for t in all_tasks() if int(t["id"]) == task_id), None)
        if task:
            async with aiohttp.ClientSession() as session:
                await process_task(message.bot, session, task, silent_seed=True)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")


async def main() -> None:
    init_db()

    bot = Bot(BOT_TOKEN, default={"parse_mode": ParseMode.HTML})
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_add_json, Command("add_json"))
    dp.message.register(cmd_list, Command("list"))
    dp.message.register(cmd_delete, Command("delete"))
    dp.message.register(cmd_checkall, Command("checkall"))
    dp.message.register(catch_json, F.text)

    scheduler.add_job(
        scheduled_check,
        "interval",
        seconds=30,
        kwargs={"bot": bot},
        id="scheduled_check",
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())