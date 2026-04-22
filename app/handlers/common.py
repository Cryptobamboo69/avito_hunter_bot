from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message) -> None:
    await message.answer(
        "Бот запущен. Используй /help, /add_json, /list, /checkall."
    )


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/add_json — добавить задачу JSON-ом\n"
        "/list — список задач\n"
        "/pause <id> — пауза\n"
        "/resume <id> — включить\n"
        "/delete <id> — удалить\n"
        "/check <id> — проверить задачу\n"
        "/checkall — проверить всё"
    )
