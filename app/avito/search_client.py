from __future__ import annotations

import asyncio
import httpx
from app.config import settings


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class AvitoSearchClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers=DEFAULT_HEADERS)
        self._lock = asyncio.Lock()

    async def fetch_search_html(self, url: str) -> str:
        async with self._lock:
            response = await self._client.get(url)
            response.raise_for_status()
            await asyncio.sleep(settings.min_request_delay_seconds)
            return response.text

    async def close(self) -> None:
        await self._client.aclose()

import aiohttp

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9"
}

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, headers=HEADERS) as response:
        return await response.text()