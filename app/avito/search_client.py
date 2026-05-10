import asyncio
import logging

import aiohttp
from playwright.async_api import async_playwright

from app.config import settings

logger = logging.getLogger(__name__)


class AvitoSearchClient:
    async def fetch_search_html(self, url: str) -> str:
        return await fetch_html(None, url)

    async def close(self) -> None:
        return None


async def fetch_html(
    session: aiohttp.ClientSession | None,
    url: str,
) -> str:

    delay = getattr(settings, "min_request_delay", 2)

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
            viewport={"width": 1365, "height": 900},
        )

        page = await context.new_page()

        try:
            logger.info("Playwright opening: %s", url)

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.wait_for_timeout(5000)

            await page.wait_for_selector(
    'a[href*="/item/"], [data-marker="item"], div[data-marker="catalog-serp"]',
    timeout=20000
)

            html = await page.content()

            logger.info(
                "Playwright fetched %s len=%s has_data_marker=%s",
                url,
                len(html or ""),
                "data-marker" in html,
            )

            await asyncio.sleep(delay)

            return html

        finally:
            await context.close()
            await browser.close()