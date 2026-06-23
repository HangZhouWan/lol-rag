"""编排器：组合各模块完成完整抓取流水线"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

from .config import OUTPUT_DIR, CONCURRENCY, REQUEST_DELAY, MAX_RETRIES, RETRY_BACKOFF
from .fetcher import Fetcher
from .parser import parse_hero_page, parse_equip_page, parse_rune_page
from .repository import FetchRepository
from .writer import (
    hero_to_markdown, equip_to_markdown, rune_to_markdown,
    write_markdown, sanitize_filename,
)
from .url_builder import build_all_urls, detect_category, get_category_dir

logger = logging.getLogger(__name__)
TZ = timezone(timedelta(hours=8))

class Orchestrator:
    def __init__(
        self,
        output_dir: str = OUTPUT_DIR,
        force: bool = False,
        concurrency: int = CONCURRENCY,
        delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        backoff: list[float] | None = None,
    ):
        self.output_dir = output_dir
        self.force = force
        self.fetcher = Fetcher(
            delay=delay, max_retries=max_retries,
            backoff=backoff, concurrency=concurrency,
        )
        self.repo = FetchRepository(
            record_path=os.path.join(output_dir, ".fetch_record.json")
        )

    def _resolve_category_dir(self, category: str) -> str:
        """Get the output directory path for a category."""
        return get_category_dir(category)

    async def run(self) -> dict:
        """执行完整抓取流水线，返回统计摘要。"""
        # 1. 加载历史记录
        self.repo.load()

        # 2. 生成 URL 列表并分类
        hero_urls, equip_urls, rune_urls = build_all_urls()
        all_urls = hero_urls + equip_urls + rune_urls

        # 3. 过滤待抓取 URL
        pending = self.repo.get_pending_urls(all_urls, force=self.force)
        skipped = len(all_urls) - len(pending)

        stats = {"total": len(all_urls), "success": 0, "failed": 0, "skipped": skipped}

        if not pending:
            logger.info("No pending URLs to fetch.")
            return stats

        # 4. 并发抓取
        results = await self.fetcher.fetch_all(pending)

        # 5-6. 逐条处理
        _CATEGORY_HANDLERS = {
            "heroes":    (parse_hero_page,  "name_cn", hero_to_markdown),
            "equipment": (parse_equip_page, "name",    equip_to_markdown),
            "runes":     (parse_rune_page,  "name",    rune_to_markdown),
        }
        for url, html, error in results:
            category = detect_category(url)

            if error:
                self.repo.record_failure(url, category, error)
                stats["failed"] += 1
                continue

            if html is None:
                self.repo.record_failure(url, category, "Empty response")
                stats["failed"] += 1
                continue

            # 解析
            try:
                parser, name_attr, formatter = _CATEGORY_HANDLERS[category]
                now = datetime.now(TZ).isoformat()
                data = parser(html, url, now)
                if data is None:
                    raise ValueError(f"Failed to parse {category} page")
                name = getattr(data, name_attr)
                content = formatter(data)
            except Exception as e:
                self.repo.record_failure(url, category, f"Parse error: {e}")
                stats["failed"] += 1
                logger.warning(f"Parse failed for {url}: {e}")
                continue

            # 写入文件
            out_dir = self._resolve_category_dir(category)
            filename = sanitize_filename(name) + ".md"
            filepath = os.path.join(out_dir, filename)
            try:
                write_markdown(content, filepath)
            except Exception as e:
                self.repo.record_failure(url, category, f"Write error: {e}")
                stats["failed"] += 1
                logger.warning(f"Write failed for {url}: {e}")
                continue

            # 记录成功
            self.repo.record_success(url, category, name, filepath)
            stats["success"] += 1
            logger.info(f"✓ {name} → {filepath}")

        # 7. 持久化记录
        self.repo.save()

        # 8. 打印摘要
        logger.info(
            f"Done. Total: {stats['total']}, "
            f"Success: {stats['success']}, "
            f"Failed: {stats['failed']}, "
            f"Skipped: {stats['skipped']}"
        )
        return stats
