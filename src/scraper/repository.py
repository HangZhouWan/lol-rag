"""抓取记录仓库：持久化抓取状态到 JSON 文件"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from .config import FETCH_RECORD_FILE, MAX_RETRIES
from .models import FetchRecord

logger = logging.getLogger(__name__)

# 东八区
TZ = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(TZ).isoformat()


class FetchRepository:
    def __init__(self, record_path: str = FETCH_RECORD_FILE):
        self._record_path = record_path
        self.records: dict[str, FetchRecord] = {}

    @property
    def record_path(self) -> str:
        return self._record_path

    def load(self) -> None:
        """从 JSON 文件加载抓取记录。"""
        if not os.path.exists(self._record_path):
            logger.info(f"No existing fetch record at {self._record_path}, starting fresh.")
            self.records = {}
            return
        with open(self._record_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.records = {url: FetchRecord.from_dict(url, data) for url, data in raw.items()}
        logger.info(f"Loaded {len(self.records)} fetch records from {self._record_path}")

    def save(self) -> None:
        """将抓取记录写回 JSON 文件。"""
        os.makedirs(os.path.dirname(self._record_path), exist_ok=True)
        data = {url: rec.to_dict() for url, rec in self.records.items()}
        with open(self._record_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.records)} fetch records to {self._record_path}")

    def should_fetch(self, url: str, force: bool = False) -> bool:
        """判断一个 URL 是否需要抓取。"""
        if force:
            return True
        if url not in self.records:
            return True

        rec = self.records[url]
        if rec.status == "success":
            if rec.output_file and os.path.exists(rec.output_file):
                return False
            return True
        if rec.status == "failed":
            return rec.retries < MAX_RETRIES
        return True

    def get_pending_urls(self, urls: list[str], force: bool = False) -> list[str]:
        """从 URL 列表中过滤出待抓取的 URL。"""
        pending = [u for u in urls if self.should_fetch(u, force)]
        total = len(urls)
        skipped = total - len(pending)
        logger.info(
            f"URL filtering: {total} total → {len(pending)} pending "
            f"({skipped} skipped)"
        )
        return pending

    def record_success(
        self, url: str, category: str, name: str, output_file: str
    ) -> None:
        """记录一次成功抓取。"""
        now = _now()
        if url in self.records:
            rec = self.records[url]
            rec.status = "success"
            rec.name = name
            rec.output_file = output_file
            rec.fetched_at = now
            rec.error = None
            rec.retries = 0
            rec.last_attempt = now
        else:
            self.records[url] = FetchRecord(
                url=url, category=category, name=name,
                output_file=output_file, fetched_at=now,
                status="success",
            )

    def record_failure(self, url: str, category: str, error: str) -> None:
        """记录一次失败抓取。"""
        now = _now()
        if url in self.records:
            rec = self.records[url]
            rec.status = "failed"
            rec.error = error
            rec.retries += 1
            rec.last_attempt = now
        else:
            self.records[url] = FetchRecord(
                url=url, category=category, status="failed",
                error=error, retries=1, last_attempt=now,
            )
