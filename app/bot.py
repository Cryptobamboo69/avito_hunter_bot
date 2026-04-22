import asyncio
import logging
import os
import json
from typing import List, Dict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("BOT_OWNER_CHAT_ID", "0"))

DATA_FILE = "data/tasks.json"


def load_tasks() -> List[Dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks: List[Dict]):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот запущен. Используй /help")


@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "/add_json — добавить задачу\n"
        "/list — список задач\n"
        "/checkall — проверить все"
    )


@dp.message(Command("add_json"))
async def add_json(message: types.Message):
    try:
        data = json.loads(message.text.replace("/add_json", "").strip())
        tasks = load_tasks()
        data["id"] = len(tasks) + 1
        tasks.append(data)
        save_tasks(tasks)
        await message.answer(f"Задача добавлена. ID: {data['id']}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@dp.message(Command("list"))
async def list_tasks(message: types.Message):
    tasks = load_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    text = "\n".join([f"{t['id']}: {t.get('url', 'no url')}" for t in tasks])
    await message.answer(text)


@dp.message(Command("checkall"))
async def check_all(message: types.Message):
    tasks = load_tasks()
    if not tasks:
        await message.answer("Нет задач")
        return

    await message.answer(f"Проверяем {len(tasks)} задач...")


async def main():
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())