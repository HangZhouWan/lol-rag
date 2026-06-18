"""HTTP 并发抓取模块：限速、重试、并发控制"""

import asyncio
import logging
import aiohttp
from src.config import REQUEST_DELAY, MAX_RETRIES, RETRY_BACKOFF, CONCURRENCY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class Fetcher:
    def __init__(
        self,
        delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        backoff: list[float] | None = None,
        concurrency: int = CONCURRENCY,
        timeout: float = REQUEST_TIMEOUT,
    ):
        self.delay = delay
        self.max_retries = max_retries
        self.backoff = backoff or RETRY_BACKOFF
        self.concurrency = concurrency
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def _rate_limit(self):
        """确保请求间隔 ≥ delay 秒"""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            wait = self._last_request_time + self.delay - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = asyncio.get_event_loop().time()

    async def fetch_one(
        self, session: aiohttp.ClientSession, url: str
    ) -> tuple[str, str | None, str | None]:
        """抓取单个 URL，失败自动重试。返回 (url, html | None, error | None)。"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                async with self._semaphore:
                    await self._rate_limit()
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            logger.debug(f"✓ {url} ({attempt + 1} attempts)")
                            return (url, html, None)
                        else:
                            last_error = f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                last_error = "Timeout"
            except aiohttp.ClientError as e:
                last_error = str(e)
            except Exception as e:
                last_error = f"Unexpected: {e}"

            if attempt < self.max_retries:
                wait = self.backoff[min(attempt, len(self.backoff) - 1)]
                logger.warning(f"✗ {url} (attempt {attempt + 1}/{self.max_retries + 1}): {last_error}, retrying in {wait}s")
                await asyncio.sleep(wait)

        logger.error(f"✗ {url}: FAILED after {self.max_retries + 1} attempts — {last_error}")
        return (url, None, last_error)

    async def fetch_all(self, urls: list[str]) -> list[tuple[str, str | None, str | None]]:
        """并发抓取所有 URL。"""
        logger.info(f"Starting fetch of {len(urls)} URLs (concurrency={self.concurrency})")
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.fetch_one(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
        return list(results)
