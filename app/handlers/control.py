from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


def _parse_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("pause"))
async def pause_task(message: Message) -> None:
    task_id = _parse_id(message)
    if task_id is None:
        await message.answer("Используй: /pause <id>")
        return
    db = message.bot.get("db")
    scheduler = message.bot.get("scheduler")
    service = message.bot.get("service")
    await db.set_enabled(task_id, False)
    scheduler.sync_jobs(await db.list_tasks(), service.check_task)
    await message.answer(f"Задача {task_id} поставлена на паузу.")


@router.message(Command("resume"))
async def resume_task(message: Message) -> None:
    task_id = _parse_id(message)
    if task_id is None:
        await message.answer("Используй: /resume <id>")
        return
    db = message.bot.get("db")
    scheduler = message.bot.get("scheduler")
    service = message.bot.get("service")
    await db.set_enabled(task_id, True)
    scheduler.sync_jobs(await db.list_tasks(), service.check_task)
    await message.answer(f"Задача {task_id} снова активна.")


@router.message(Command("delete"))
async def delete_task(message: Message) -> None:
    task_id = _parse_id(message)
    if task_id is None:
        await message.answer("Используй: /delete <id>")
        return
    db = message.bot.get("db")
    scheduler = message.bot.get("scheduler")
    service = message.bot.get("service")
    await db.delete_task(task_id)
    scheduler.sync_jobs(await db.list_tasks(), service.check_task)
    await message.answer(f"Задача {task_id} удалена.")


@router.message(Command("check"))
async def check_one(message: Message) -> None:
    task_id = _parse_id(message)
    if task_id is None:
        await message.answer("Используй: /check <id>")
        return
    service = message.bot.get("service")
    count = await service.check_task(task_id)
    await message.answer(f"Проверка завершена. Новых совпадений: {count}")


@router.message(Command("checkall"))
async def check_all(message: Message) -> None:
    db = message.bot.get("db")
    service = message.bot.get("service")
    total = 0
    for task in await db.list_tasks():
        if task.enabled and task.id is not None:
            total += await service.check_task(task.id)
    await message.answer(f"Проверка всех задач завершена. Новых совпадений: {total}")
