from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse, urlunparse

import aiohttp
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def to_mobile_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.startswith("www.avito.ru"):
        return urlunparse(parsed._replace(netloc="m.avito.ru"))
    return url


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
            html = await self._fetch(url)

            if not looks_like_avito_results(html):
                mobile_url = to_mobile_url(url)
                logger.warning("Main Avito HTML looks empty, trying mobile URL: %s", mobile_url)
                html2 = await self._fetch(mobile_url)
                if len(html2) > len(html):
                    html = html2

            await asyncio.sleep(getattr(settings, "min_request_delay", 2))
            return html

    async def _fetch(self, url: str) -> str:
        response = await self._client.get(url)
        logger.info("Fetched %s status=%s len=%s", url, response.status_code, len(response.text))
        response.raise_for_status()
        return response.text

    async def close(self) -> None:
        await self._client.aclose()


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    html = await _fetch_aiohttp(session, url)

    if not looks_like_avito_results(html):
        mobile_url = to_mobile_url(url)
        logger.warning("Main Avito HTML looks empty, trying mobile URL: %s", mobile_url)
        html2 = await _fetch_aiohttp(session, mobile_url)
        if len(html2) > len(html):
            html = html2

    return html


async def _fetch_aiohttp(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(
        url,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=30),
        allow_redirects=True,
    ) as response:
        text = await response.text()
        logger.info("Fetched %s status=%s len=%s", url, response.status, len(text))
        response.raise_for_status()
        return text


def looks_like_avito_results(html: str) -> bool:
    if not html:
        return False

    h = html.lower()

    if "data-marker" in h:
        return True

    if "__initialdata__" in h or "__initial_data__" in h:
        return True

    if "items" in h and "avito" in h:
        return True

    return False