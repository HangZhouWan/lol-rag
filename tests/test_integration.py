"""集成测试：验证各模块协同工作"""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, patch

from src.scraper.orchestrator import Orchestrator
from src.scraper.writer import sanitize_filename, hero_to_markdown, write_markdown, equip_to_markdown, rune_to_markdown
from src.scraper.models import Hero, Equipment, Rune, Skill
from src.scraper.url_builder import detect_category, build_hero_urls


class TestIntegration:
    """端到端流程测试"""

    def test_url_to_markdown_pipeline_hero(self):
        """验证：URL 构造 → 分类识别 → Markdown 生成 的串联流程"""
        urls = build_hero_urls()
        assert len(urls) == 153
        for url in urls[:5]:
            assert detect_category(url) == "heroes"

        # 模拟解析后的数据
        hero = Hero(
            name_cn="安妮", name_en="Annie", title="黑暗之女 安妮",
            image_url="https://img.example.com/annie.png",
            role="法师", background="安妮是一个强大的火系法师。",
            initial_attrs={"攻击力": "52", "生命值": "524"},
            max_attrs={"攻击力": "98", "生命值": "1980"},
            passive_skill=Skill(name="嗜火", icon_url="https://img.example.com/p.png",
                                description="每施放4次技能后，下一次伤害技能会眩晕目标。"),
            skills=[Skill(name="碎裂之火", icon_url="https://img.example.com/q.png",
                          description="投出一团火球。", cost="60/65/70/75/80 法力",
                          cooldown="4秒", cast_range="625")],
            source_url=urls[0], fetched_at="2026-06-18T10:00:00+08:00",
        )

        md = hero_to_markdown(hero)
        assert "# 安妮 — Annie" in md
        assert "来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>" in md

        # 写入临时目录
        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, sanitize_filename("安妮") + ".md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                written = f.read()
            assert "安妮" in written

    def test_url_to_markdown_pipeline_equip(self):
        """验证装备完整流程"""
        equip = Equipment(
            name="冰霜之心", icon_url="https://img.example.com/ice.png",
            tier="传说", price="2700",
            base_attrs=["+400 法力值", "+20 技能急速", "+50 护甲"],
            passive_effect="坚如磐石：使受到的伤害减少",
            recipe=["冰川圆盾", "守望者铠甲"],
            recommended_heroes=["盖伦"],
            source_url="https://www.ali213.net/zt/LOL/wiki/zb1.html",
            fetched_at="2026-06-18T10:00:00+08:00",
        )
        md = equip_to_markdown(equip)
        assert "# 冰霜之心" in md
        assert "**等级**: 传说" in md
        assert "**售价**: 2700" in md
        assert "+400 法力值" in md
        assert "坚如磐石" in md
        assert "冰川圆盾" in md

        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, "冰霜之心.md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)

    def test_url_to_markdown_pipeline_rune(self):
        """验证符文完整流程"""
        rune = Rune(
            name="强攻", icon_url="https://img.example.com/pta.png",
            category="精密", tier="基石",
            description="用3次连续的普攻命中一名敌方英雄",
            source_url="https://www.ali213.net/zt/LOL/wiki/fw1.html",
            fetched_at="2026-06-18T10:00:00+08:00",
        )
        md = rune_to_markdown(rune)
        assert "# 强攻" in md
        assert "**类别**: 精密" in md
        assert "**等级**: 基石" in md

        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, "强攻.md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)

    def test_markdown_ends_with_metadata(self):
        """验证所有输出的 Markdown 均包含来源和时间的元数据"""
        hero = Hero("test", "test", "test", "", "", "",
                    {}, {}, None, [],
                    source_url="http://test.com/yx1.html",
                    fetched_at="2026-06-18T10:00:00+08:00")
        md = hero_to_markdown(hero)
        assert "来源: <http://test.com/yx1.html>" in md
        assert "抓取时间: 2026-06-18T10:00:00+08:00" in md

    @pytest.mark.asyncio
    async def test_orchestrator_skips_successful_urls(self):
        """集成测试：Orchestrator 应跳过已成功抓取的 URL"""
        with tempfile.TemporaryDirectory() as d:
            orch = Orchestrator(output_dir=d, force=False)
            # 预填记录
            hero_dir = os.path.join(d, "heroes")
            os.makedirs(hero_dir, exist_ok=True)
            filepath = os.path.join(hero_dir, "安妮.md")
            with open(filepath, "w") as f:
                f.write("test")

            orch.repo.record_success(
                "https://www.ali213.net/zt/LOL/wiki/yx1.html",
                "heroes", "安妮", filepath,
            )
            orch.repo.save()  # 持久化，以便 run() 中的 load() 能读取到

            orch.fetcher.fetch_all = AsyncMock(return_value=[])

            stats = await orch.run()

            # yx1 不应出现在 fetch_all 调用中
            if orch.fetcher.fetch_all.called:
                called_urls = orch.fetcher.fetch_all.call_args[0][0]
                assert "https://www.ali213.net/zt/LOL/wiki/yx1.html" not in called_urls

            assert stats["skipped"] >= 1
