import asyncio
import json
import logging
import os
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("BOT_OWNER_CHAT_ID", "0") or 0)
DATA_FILE = "data/tasks.json"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# user_id -> waiting mode
user_states: Dict[int, str] = {}


def ensure_data_dir() -> None:
    os.makedirs("data", exist_ok=True)


def load_tasks() -> List[Dict]:
    ensure_data_dir()
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_tasks(tasks: List[Dict]) -> None:
    ensure_data_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def next_task_id(tasks: List[Dict]) -> int:
    if not tasks:
        return 1
    return max(int(t.get("id", 0)) for t in tasks) + 1


@dp.message(Command("start"))
async def start_cmd(message: Message) -> None:
    await message.answer("Бот запущен. Используй /help")


@dp.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "/add_json — добавить задачу JSON-ом\n"
        "/list — список задач\n"
        "/checkall — проверить все задачи\n"
        "/delete <id> — удалить задачу"
    )


@dp.message(Command("add_json"))
async def add_json_cmd(message: Message) -> None:
    user_states[message.from_user.id] = "waiting_json"
    await message.answer(
        "Пришли JSON следующим сообщением.\n\n"
        "Пример:\n"
        '{"name":"nespresso","search_url":"https://www.avito.ru/moskva?q=nespresso+essenza+mini+c30&priceMax=3000&user=1","max_price":3000,"check_interval_sec":30}'
    )


@dp.message(Command("list"))
async def list_cmd(message: Message) -> None:
    tasks = load_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    lines = []
    for t in tasks:
        lines.append(
            f"ID {t.get('id')} | {t.get('name', 'без имени')}\n"
            f"URL: {t.get('search_url', '-')}\n"
            f"max_price={t.get('max_price')} | every={t.get('check_interval_sec', 30)}s"
        )

    await message.answer("\n\n".join(lines)[:4000])


@dp.message(Command("delete"))
async def delete_cmd(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /delete <id>")
        return

    task_id = int(parts[1])
    tasks = load_tasks()
    new_tasks = [t for t in tasks if int(t.get("id", 0)) != task_id]

    if len(new_tasks) == len(tasks):
        await message.answer("Задача не найдена")
        return

    save_tasks(new_tasks)
    await message.answer(f"Задача {task_id} удалена")


@dp.message(Command("checkall"))
async def checkall_cmd(message: Message) -> None:
    tasks = load_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return

    await message.answer(f"Проверяем {len(tasks)} задач...")


@dp.message(F.text)
async def text_handler(message: Message) -> None:
    state = user_states.get(message.from_user.id)

    if state != "waiting_json":
        return

    raw = (message.text or "").strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        await message.answer(f"Ошибка JSON: {e}")
        return

    required = ["name", "search_url"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        await message.answer(f"Не хватает полей: {', '.join(missing)}")
        return

    tasks = load_tasks()

    task = {
        "id": next_task_id(tasks),
        "name": str(data["name"]).strip(),
        "search_url": str(data["search_url"]).strip(),
        "max_price": data.get("max_price"),
        "check_interval_sec": int(data.get("check_interval_sec", 30) or 30),
    }

    tasks.append(task)
    save_tasks(tasks)
    user_states.pop(message.from_user.id, None)

    await message.answer(f"Задача добавлена. ID: {task['id']}")


async def scheduled_check() -> None:
    tasks = load_tasks()
    if not tasks:
        return
    logger.info("Scheduled check: %s tasks", len(tasks))


async def main() -> None:
    ensure_data_dir()
    scheduler.add_job(scheduled_check, "interval", seconds=30, id="scheduled_check", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())