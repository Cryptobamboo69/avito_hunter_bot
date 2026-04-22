[22.04.2026 15:12] PF: from future import annotations

import asyncio
import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class ContextBot(Bot):
    """
    Совместимый бот для старого кода, который ожидает:
      - bot["db"] = ...
      - bot["scheduler"] = ...
      - bot.get("db")
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ctx: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        return self._ctx[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._ctx[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._ctx.get(key, default)


def _maybe_load_env() -> None:
    if load_dotenv is None:
        return

    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


async def _call_maybe_async(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _build_db() -> Any:
    """
    Пытаемся инициализировать БД максимально бережно,
    не зная точной реализации database.py.
    """
    db_module = importlib.import_module("app.database")
    db_path = os.getenv("DB_PATH", "data/bot.db")

    # Вариант 1: есть класс Database
    if hasattr(db_module, "Database"):
        Database = getattr(db_module, "Database")

        db = None
        init_attempts = [
            lambda: Database(db_path),
            lambda: Database(path=db_path),
            lambda: Database(db_path=db_path),
            lambda: Database(),
        ]

        for attempt in init_attempts:
            try:
                db = attempt()
                break
            except TypeError:
                continue

        if db is None:
            raise RuntimeError("Could not initialize Database class")

        for method_name in ("connect", "init", "initialize", "setup", "startup"):
            if hasattr(db, method_name):
                await _call_maybe_async(getattr(db, method_name))

        return db

    # Вариант 2: есть фабрика
    for factory_name in ("create_db", "init_db", "get_db"):
        if hasattr(db_module, factory_name):
            factory = getattr(db_module, factory_name)
            try:
                return await _call_maybe_async(factory, db_path)
            except TypeError:
                return await _call_maybe_async(factory)

    raise RuntimeError("Could not find a database initializer in app.database")


async def _build_scheduler(bot: ContextBot, db: Any) -> Any:
    """
    Пытаемся инициализировать scheduler.py максимально гибко.
    """
    sched_module = importlib.import_module("app.scheduler")

    # Вариант 1: фабрика
    for factory_name in ("create_scheduler", "get_scheduler", "build_scheduler"):
        if hasattr(sched_module, factory_name):
            factory = getattr(sched_module, factory_name)
            attempts = [
                lambda: factory(bot=bot, db=db),
                lambda: factory(db=db, bot=bot),
                lambda: factory(bot, db),
                lambda: factory(db),
                lambda: factory(),
            ]
            for attempt in attempts:
                try:
                    scheduler = await _call_maybe_async(attempt)
                    return scheduler
                except TypeError:
                    continue

    # Вариант 2: класс Scheduler
    if hasattr(sched_module, "Scheduler"):
[22.04.2026 15:12] PF: Scheduler = getattr(sched_module, "Scheduler")
        attempts = [
            lambda: Scheduler(bot=bot, db=db),
            lambda: Scheduler(db=db, bot=bot),
            lambda: Scheduler(bot, db),
            lambda: Scheduler(db),
            lambda: Scheduler(),
        ]
        for attempt in attempts:
            try:
                scheduler = attempt()
                return scheduler
            except TypeError:
                continue

    logger.warning("Scheduler was not initialized from app.scheduler")
    return None


def _include_routers(dp: Dispatcher) -> None:
    """
    Подключаем роутеры из известных модулей.
    """
    module_names = [
        "app.handlers.common",
        "app.handlers.add_task",
        "app.handlers.control",
        "app.handlers.list_tasks",
        "app.handlers",
    ]

    attached = 0

    for module_name in module_names:
        try:
            mod = importlib.import_module(module_name)
        except Exception as e:
            logger.warning("Could not import %s: %s", module_name, e)
            continue

        # Самый типичный случай
        if hasattr(mod, "router"):
            try:
                dp.include_router(getattr(mod, "router"))
                attached += 1
                continue
            except Exception as e:
                logger.warning("Could not attach router from %s: %s", module_name, e)

        # Если есть список роутеров
        if hasattr(mod, "routers"):
            try:
                for r in getattr(mod, "routers"):
                    dp.include_router(r)
                    attached += 1
                continue
            except Exception as e:
                logger.warning("Could not attach routers from %s: %s", module_name, e)

        # Если есть setup(dispatcher)
        if hasattr(mod, "setup"):
            try:
                getattr(mod, "setup")(dp)
                attached += 1
                continue
            except Exception as e:
                logger.warning("Could not call setup() from %s: %s", module_name, e)

    if attached == 0:
        raise RuntimeError("No routers were attached to Dispatcher")


async def main() -> None:
    _maybe_load_env()

    token = _get_required_env("BOT_TOKEN")

    bot = ContextBot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # БД
    db = await _build_db()
    bot["db"] = db

    # Планировщик
    scheduler = await _build_scheduler(bot, db)
    if scheduler is not None:
        bot["scheduler"] = scheduler

    # Для кода, который может брать зависимости из dispatcher
    dp.workflow_data["db"] = db
    dp.workflow_data["scheduler"] = scheduler
    dp.workflow_data["bot_ctx"] = bot

    # Роутеры
    _include_routers(dp)

    # Запуск scheduler, если у него есть start/startup
    if scheduler is not None:
        for method_name in ("start", "startup"):
            if hasattr(scheduler, method_name):
                try:
                    await _call_maybe_async(getattr(scheduler, method_name))
                    break
                except Exception as e:
                    logger.warning("Could not start scheduler: %s", e)

    logger.info("Bot is starting polling")
    try:
        await dp.start_polling(bot)
    finally:
        # Остановка scheduler
        if scheduler is not None:
            for method_name in ("shutdown", "stop", "close"):
                if hasattr(scheduler, method_name):
                    try:
                        await _call_maybe_async(getattr(scheduler, method_name))
                        break
                    except Exception as e:
                        logger.warning("Could not stop scheduler: %s", e)

        # Закрытие БД
        if db is not None:
            for method_name in ("close", "disconnect", "shutdown"):
                if hasattr(db, method_name):
                    try:
                        await _call_maybe_async(getattr(db, method_name))
                        break
                    except Exception as e:
[22.04.2026 15:12] PF: logger.warning("Could not close db: %s", e)

        await bot.session.close()


if name == "__main__":
    asyncio.run(main())
