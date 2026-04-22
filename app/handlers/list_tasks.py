from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("list"))
async def list_tasks(message: Message) -> None:
    db = message.bot.get("db")
    tasks = await db.list_tasks()
    if not tasks:
        await message.answer("Задач пока нет.")
        return
    chunks = []
    for task in tasks:
        chunks.append(
            f"ID {task.id} | {'ON' if task.enabled else 'OFF'}\n"
            f"{task.name}\n"
            f"URL: {task.search_url}\n"
            f"max_price={task.max_price} | city={task.city} | min_score={task.min_score} | every={task.check_interval_sec}s"
        )
    await message.answer("\n\n".join(chunks))
