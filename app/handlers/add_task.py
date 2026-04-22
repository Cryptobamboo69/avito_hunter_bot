from __future__ import annotations

import json
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from app.models import SearchTask

router = Router()


class AddTaskState(StatesGroup):
    waiting_json = State()


@router.message(Command("add_json"))
async def start_add_json(message: Message, state: FSMContext) -> None:
    await state.set_state(AddTaskState.waiting_json)
    await message.answer(
        "Пришли JSON задачи одним сообщением. Пример есть в README и /help."
    )


@router.message(AddTaskState.waiting_json)
async def finish_add_json(message: Message, state: FSMContext) -> None:
    try:
        payload = json.loads(message.text)
        task = SearchTask(
            id=None,
            name=payload["name"],
            search_url=payload["search_url"],
            max_price=payload.get("max_price"),
            city=payload.get("city"),
            include_keywords=payload.get("include_keywords", []),
            exclude_keywords=payload.get("exclude_keywords", []),
            brand_filters=payload.get("brand_filters", []),
            size_filters=payload.get("size_filters", []),
            min_score=payload.get("min_score", 6),
            check_interval_sec=payload.get("check_interval_sec", 120),
            enabled=payload.get("enabled", True),
        )
    except Exception as exc:
        await message.answer(f"Не смог разобрать JSON: {exc}")
        return

    db = message.bot.get("db")
    scheduler = message.bot.get("scheduler")
    service = message.bot.get("service")
    task_id = await db.add_task(task)
    await state.clear()
    await message.answer(f"Задача добавлена. ID: {task_id}")
    tasks = await db.list_tasks()
    scheduler.sync_jobs(tasks, service.check_task)
