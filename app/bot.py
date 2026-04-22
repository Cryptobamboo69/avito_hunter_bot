from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.avito.search_client import AvitoSearchClient
from app.config import settings
from app.database import Database
from app.handlers import add_task, list_tasks, control, common
from app.scheduler import PollingScheduler
from app.service import MonitorService


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main() -> None:
    setup_logging()
    settings.validate()

    db = Database(settings.database_path)
    await db.init()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    client = AvitoSearchClient()
    scheduler = PollingScheduler()
    service = MonitorService(bot=bot, db=db, client=client, owner_chat_id=settings.bot_owner_chat_id)

    bot["db"] = db
    bot["scheduler"] = scheduler
    bot["service"] = service

    dp.include_router(common.router)
    dp.include_router(add_task.router)
    dp.include_router(list_tasks.router)
    dp.include_router(control.router)

    scheduler.sync_jobs(await db.list_tasks(), service.check_task)

    try:
        await dp.start_polling(bot)
    finally:
        await scheduler.shutdown()
        await client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
