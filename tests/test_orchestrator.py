import asyncio
import tempfile
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.orchestrator import Orchestrator


class TestOrchestrator:
    @pytest.fixture
    def output_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.mark.asyncio
    async def test_run_respects_skipped_urls(self, output_dir):
        """已成功的 URL 应被跳过，不被 fetcher 调用。"""
        orch = Orchestrator(output_dir=output_dir, force=False)
        # 预填一条成功记录
        orch.repo.record_success(
            "https://www.ali213.net/zt/LOL/wiki/yx1.html",
            "heroes", "安妮",
            os.path.join(output_dir, "heroes", "安妮.md"),
        )
        # 创建对应的输出文件
        os.makedirs(os.path.join(output_dir, "heroes"), exist_ok=True)
        with open(os.path.join(output_dir, "heroes", "安妮.md"), "w") as f:
            f.write("test")

        # 持久化记录到磁盘，避免 run() 内 load() 清空内存记录
        orch.repo.save()

        orch.fetcher.fetch_all = AsyncMock(return_value=[])

        stats = await orch.run()
        # yx1 已被跳过，不应出现在传给 fetch_all 的 URL 中
        call_args = orch.fetcher.fetch_all.call_args[0][0]
        assert "https://www.ali213.net/zt/LOL/wiki/yx1.html" not in call_args
        assert stats["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_run_counts_success_and_failure(self, output_dir):
        """验证成功/失败统计正确。"""
        orch = Orchestrator(output_dir=output_dir, force=True, concurrency=1)

        async def mock_fetch_all(urls):
            results = []
            for url in urls:
                if "yx1" in url:
                    results.append((url, "<html>hero1</html>", None))
                elif "yx2" in url:
                    results.append((url, None, "Connection error"))
                else:
                    results.append((url, "<html>default</html>", None))
            return results

        orch.fetcher.fetch_all = mock_fetch_all

        mock_return = MagicMock(
            name_cn="TestHero", name_en="Test",
            image_url="", title="", role="", background="",
            initial_attrs={}, max_attrs={},
            passive_skill=None, skills=[],
            source_url="", fetched_at="",
        )
        # 设置 .name 属性给 equipment/rune 解析使用
        mock_return.name = "TestItem"

        with (
            patch("src.orchestrator.parse_hero_page", return_value=mock_return),
            patch("src.orchestrator.parse_equip_page", return_value=mock_return),
            patch("src.orchestrator.parse_rune_page", return_value=mock_return),
            patch("src.orchestrator.hero_to_markdown", return_value="# markdown"),
            patch("src.orchestrator.equip_to_markdown", return_value="# markdown"),
            patch("src.orchestrator.rune_to_markdown", return_value="# markdown"),
            patch("src.orchestrator.write_markdown"),
        ):
            stats = await orch.run()

        assert stats["total"] > 0
        assert "success" in stats
        assert "failed" in stats
        assert "skipped" in stats
        assert stats["success"] + stats["failed"] + stats["skipped"] == stats["total"]
