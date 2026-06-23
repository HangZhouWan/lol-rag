"""CLI 入口：命令行参数解析与编排器启动"""

import argparse
import asyncio
import logging
import sys

from src.scraper.config import OUTPUT_DIR, CONCURRENCY, REQUEST_DELAY, MAX_RETRIES
from src.scraper.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def _positive_int(v: str) -> int:
    """Argparse type validator: integer >= 1."""
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {n}")
    return n


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        prog="lol-scraper",
        description="LOL Wiki 资料抓取器 — 为 RAG 系统准备游戏资料数据",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制重新抓取全部页面（忽略已有的成功记录）",
    )
    parser.add_argument(
        "--concurrency", type=_positive_int, default=CONCURRENCY,
        help=f"并发请求数上限（默认: {CONCURRENCY}）",
    )
    parser.add_argument(
        "--output-dir", type=str, default=OUTPUT_DIR,
        help=f"输出目录（默认: {OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--delay", type=float, default=REQUEST_DELAY,
        help=f"请求间延迟秒数（默认: {REQUEST_DELAY}）",
    )
    parser.add_argument(
        "--max-retries", type=int, default=MAX_RETRIES,
        help=f"单页最大重试次数（默认: {MAX_RETRIES}）",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认: INFO）",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    """主入口。"""
    args = parse_args(argv)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("LOL Wiki Scraper — Starting")
    logger.info(f"  Force: {args.force}")
    logger.info(f"  Concurrency: {args.concurrency}")
    logger.info(f"  Output: {args.output_dir}")
    logger.info(f"  Delay: {args.delay}s")
    logger.info(f"  Max retries: {args.max_retries}")
    logger.info("=" * 60)

    orch = Orchestrator(
        output_dir=args.output_dir,
        force=args.force,
        concurrency=args.concurrency,
        delay=args.delay,
        max_retries=args.max_retries,
    )

    stats = await orch.run()

    logger.info("=" * 60)
    logger.info(
        f"Complete — "
        f"Total: {stats['total']}, "
        f"Success: {stats['success']}, "
        f"Failed: {stats['failed']}, "
        f"Skipped: {stats['skipped']}"
    )
    logger.info("=" * 60)

    # 如果有失败，以非零退出码退出
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
