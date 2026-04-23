import os
import json
import asyncio
import logging
import sqlite3
from contextlib import closing

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

from app.service import process_task


TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db").strip()

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is empty")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher()

waiting_for_json: set[int] = set()


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(get_conn()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                search_url TEXT NOT NULL,
                max_price INTEGER,
                check_interval_sec INTEGER DEFAULT 180
            )
            """
        )
        conn.commit()


def add_task(name: str, search_url: str, max_price: int | None, check_interval_sec: int):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (name, search_url, max_price, check_interval_sec)
            VALUES (?, ?, ?, ?)
            """,
            (name, search_url, max_price, check_interval_sec),
        )
        conn.commit()
        return cur.lastrowid


def list_tasks():
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            SELECT id, name, search_url, max_price, check_interval_sec
            FROM tasks
            ORDER BY id
            """
        )
        return cur.fetchall()


def delete_task(task_id: int):
    with closing(get_conn()) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот запущен.\n\n"
        "Команды:\n"
        "/add_json — добавить задачу JSON\n"
        "/list — список задач\n"
        "/delete ID — удалить задачу\n"
        "/checkall — проверить все задачи"
    )


@dp.message(Command("add_json"))
async def cmd_add_json(message: types.Message):
    waiting_for_json.add(message.chat.id)
    await message.answer(
        "Пришли JSON следующим сообщением.\n\n"
        "Пример:\n"
        '{"name":"nespresso_c30","search_url":"https://www.avito.ru/moskva?q=nespresso+essenza+mini+c30+рабочая+без+дефектов&priceMax=3000","max_price":3000,"check_interval_sec":180}'
    )


@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    tasks = list_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    lines = []
    for row in tasks:
        lines.append(
            f"ID {row[0]} | {row[1]}\n"
            f"URL: {row[2]}\n"
            f"max_price={row[3]} | every={row[4]}s"
        )

    await message.answer("\n\n".join(lines))


@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: /delete ID")
        return

    try:
        task_id = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return

    ok = delete_task(task_id)
    await message.answer("Удалено." if ok else "Не найдено.")


@dp.message(Command("checkall"))
async def cmd_checkall(message: types.Message):
    tasks = list_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    await message.answer(f"Проверяем {len(tasks)} задач...")

    async with aiohttp.ClientSession() as session:
        for row in tasks:
            task = {
                "id": row[0],
                "name": row[1],
                "search_url": row[2],
                "max_price": row[3],
                "check_interval_sec": row[4],
            }
            await process_task(message, session, task)
            await asyncio.sleep(1)


@dp.message()
async def handle_json(message: types.Message):
    if message.chat.id not in waiting_for_json:
        return

    raw = (message.text or "").strip()

    try:
        data = json.loads(raw)

        name = str(data["name"]).strip()
        search_url = str(data["search_url"]).strip()
        max_price = data.get("max_price")
        check_interval_sec = int(data.get("check_interval_sec", 180))

        if not name:
            raise ValueError("name пустой")
        if not search_url:
            raise ValueError("search_url пустой")

        if max_price is not None:
            max_price = int(max_price)

        task_id = add_task(
            name=name,
            search_url=search_url,
            max_price=max_price,
            check_interval_sec=check_interval_sec,
        )

        waiting_for_json.discard(message.chat.id)
        await message.answer(f"Задача добавлена. ID: {task_id}")

    except Exception as e:
        await message.answer(f"Ошибка JSON: {e}")


async def main():
    init_db()

    await bot.delete_webhook(drop_pending_updates=True)

    while True:
        try:
            logger.info("Bot started")
            await dp.start_polling(bot)
        except TelegramBadRequest as e:
            if "logged out" in str(e).lower():
                logger.warning("Bot logged out, retry in 5 sec")
                await asyncio.sleep(5)
                continue
            raise
        except Exception as e:
            logger.exception("Bot crashed: %s", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())