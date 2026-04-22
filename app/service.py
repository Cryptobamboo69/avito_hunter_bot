from __future__ import annotations

import logging
from aiogram import Bot
from app.avito.parser import parse_search_results
from app.avito.search_client import AvitoSearchClient
from app.database import Database
from app.filters.matcher import match_listing
from app.models import Listing, SearchTask

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, bot: Bot, db: Database, client: AvitoSearchClient, owner_chat_id: int) -> None:
        self.bot = bot
        self.db = db
        self.client = client
        self.owner_chat_id = owner_chat_id

    async def check_task(self, task_id: int) -> int:
        task = await self.db.get_task(task_id)
        if task is None or task.id is None or not task.enabled:
            return 0
        logger.info("Checking task %s: %s", task.id, task.name)
        html = await self.client.fetch_search_html(task.search_url)
        listings = parse_search_results(html)
        found = 0
        for listing in listings[:50]:
            if await self.db.has_seen(task.id, listing.external_id):
                continue
            result = match_listing(task, listing)
            await self.db.mark_seen(task.id, listing.external_id, listing.url)
            if not result.matched:
                continue
            await self._send_match(task, listing, result.score, result.reasons)
            found += 1
        return found

    async def _send_match(self, task: SearchTask, listing: Listing, score: int, reasons: list[str]) -> None:
        price = f"{listing.price} ₽" if listing.price is not None else "цена не распознана"
        location = listing.location or "локация не распознана"
        reasons_text = "\n".join(f"• {reason}" for reason in reasons[:6])
        text = (
            f"🔔 <b>{task.name}</b>\n"
            f"<b>{listing.title}</b>\n"
            f"Цена: {price}\n"
            f"Город: {location}\n"
            f"Score: {score}\n\n"
            f"Почему прошло:\n{reasons_text}\n\n"
            f"{listing.url}"
        )
        await self.bot.send_message(self.owner_chat_id, text, disable_web_page_preview=False)
