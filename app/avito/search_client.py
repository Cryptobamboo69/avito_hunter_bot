from __future__ import annotations

import asyncio
import aiohttp
import httpx

from app.config import settings


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


class AvitoSearchClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30,
            headers=HEADERS,
            follow_redirects=True,
        )
        self._lock = asyncio.Lock()

    async def fetch_search_html(self, url: str) -> str:
        async with self._lock:
            response = await self._client.get(url)
            response.raise_for_status()

            await asyncio.sleep(settings.min_request_delay)

            return response.text

    async def close(self) -> None:
        await self._client.aclose()


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(
        url,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=30),
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        return await response.text()