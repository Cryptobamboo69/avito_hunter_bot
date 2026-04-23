import asyncio
import logging
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from app.avito.search_client import fetch_html
from app.avito.parser import parse_search_results

TOKEN = "8782414898:AAHP3UM4xj5kEWt0vTkgAM_UuXXqMYBA6ws"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

# Хранилище задач (временно в памяти)
tasks = []
task_id_counter = 1


# ======================
# КОМАНДЫ
# ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот запущен 🚀\n\nКоманды:\n/add\n/list\n/checkall")


@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    global task_id_counter

    text = message.text.replace("/add", "").strip()
    if not text:
        await message.answer("Пример:\n/add nespresso https://avito.ru/... 3000")
        return

    try:
        name, url, price = text.split(" ", 2)
        price = int(price)
    except:
        await message.answer("Формат:\n/add название URL цена")
        return

    task = {
        "id": task_id_counter,
        "name": name,
        "url": url,
        "max_price": price,
    }

    tasks.append(task)
    task_id_counter += 1

    await message.answer(f"Задача добавлена. ID: {task['id']}")


@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    if not tasks:
        await message.answer("Нет задач")
        return

    text = ""
    for t in tasks:
        text += f"ID {t['id']} | {t['name']}\n"
        text += f"{t['url']}\n"
        text += f"max_price={t['max_price']}\n\n"

    await message.answer(text)


@dp.message(Command("checkall"))
async def cmd_checkall(message: types.Message):
    await message.answer(f"Проверяем {len(tasks)} задач...")

    async with aiohttp.ClientSession() as session:
        for task in tasks:
            try:
                html = await fetch_html(session, task["url"])
                items = parse_search_results(html)

                sent = 0

                for item in items:
                    if item.price is None:
                        continue

                    if item.price > task["max_price"]:
                        continue

                    text = f"""<b>{task['name']}</b>

{item.title}
Цена: {item.price} ₽
{item.url}
"""

                    await message.answer(text)
                    sent += 1

                    if sent >= 5:
                        break

            except Exception as e:
                await message.answer(f"Ошибка в задаче {task['name']}: {e}")


# ======================
# СТАРТ БОТА (ВАЖНО)
# ======================

async def main():
    while True:
        try:
            print("🚀 Starting bot...")
            await dp.start_polling(bot)
        except TelegramBadRequest as e:
            if "logged out" in str(e).lower():
                print("⚠️ Logged out, retry...")
                await asyncio.sleep(3)
                continue
            raise
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())