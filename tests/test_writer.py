# tests/test_writer.py
import os
import tempfile
import pytest
from src.scraper.writer import hero_to_markdown, equip_to_markdown, rune_to_markdown, write_markdown, sanitize_filename
from src.scraper.models import Hero, Equipment, Rune, Skill


class TestSanitizeFilename:
    def test_removes_slashes(self):
        assert sanitize_filename("a/b") == "ab"

    def test_keeps_chinese(self):
        assert sanitize_filename("黑暗之女") == "黑暗之女"

    def test_removes_other_special_chars(self):
        cleaned = sanitize_filename('test<>:"/\\|?*file')
        assert ">" not in cleaned
        assert "<" not in cleaned
        assert '"' not in cleaned


class TestHeroToMarkdown:
    def test_full_hero(self):
        hero = Hero(
            name_cn="祖安怒兽",
            name_en="沃里克",
            title="祖安怒兽 沃里克",
            image_url="https://example.com/warwick.png",
            role="战士",
            background="沃里克是祖安城中一个传奇人物。",
            initial_attrs={"攻击力": "65", "生命值": "620"},
            max_attrs={"攻击力": "115", "生命值": "2268"},
            passive_skill=Skill(name="血之饥渴", icon_url="https://x.com/p.png",
                                description="普攻造成额外魔法伤害"),
            skills=[Skill(name="野兽之口", icon_url="https://x.com/q.png",
                          description="向前猛扑", cost="50/60/70/80/90 法力",
                          cooldown="6秒", cast_range="350")],
            source_url="https://www.ali213.net/zt/LOL/wiki/yx1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = hero_to_markdown(hero)
        assert "# 祖安怒兽 — 沃里克" in md
        assert "![祖安怒兽](https://example.com/warwick.png)" in md
        assert "**定位**: 战士" in md
        assert "## 背景故事" in md
        assert "沃里克是祖安城中一个传奇人物。" in md
        assert "| 攻击力 | 65 | 115 |" in md
        assert "### 被动：血之饥渴" in md
        assert "### Q：野兽之口" in md
        assert "**冷却**: 6秒" in md
        assert "**范围**: 350" in md
        assert "来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>" in md
        assert "抓取时间: 2026-06-18T10:30:00+08:00" in md

    def test_hero_no_passive(self):
        hero = Hero(
            name_cn="测试", name_en="Test", title="测试英雄",
            image_url="", role="法师", background="",
            initial_attrs={}, max_attrs={},
            passive_skill=None, skills=[],
            source_url="http://x.com", fetched_at="2026-01-01T00:00:00+08:00",
        )
        md = hero_to_markdown(hero)
        assert "## 技能" not in md  # no skills section if empty
        assert "## 属性" not in md  # no attrs section if empty
        assert "测试英雄" in md


class TestEquipToMarkdown:
    def test_full_equip(self):
        equip = Equipment(
            name="冰霜之心",
            icon_url="https://x.com/ice.png",
            tier="传说",
            price="2700",
            base_attrs=["+400 法力值", "+20 技能急速", "+50 护甲"],
            active_effect=None,
            passive_effect="坚如磐石：使受到的伤害减少",
            mythic_bonus="+5 技能急速",
            recipe=["冰川圆盾", "守望者铠甲", "900 金币"],
            recommended_heroes=["盖伦", "德莱厄斯"],
            source_url="https://www.ali213.net/zt/LOL/wiki/zb1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = equip_to_markdown(equip)
        assert "# 冰霜之心" in md
        assert "**等级**: 传说" in md
        assert "**售价**: 2700" in md
        assert "+400 法力值" in md
        assert "### 被动效果" in md
        assert "坚如磐石" in md
        assert "### 神话加成" in md
        assert "### 合成路线" in md
        assert "冰川圆盾" in md
        assert "### 推荐英雄" in md
        assert "盖伦" in md


class TestRuneToMarkdown:
    def test_full_rune(self):
        rune = Rune(
            name="强攻",
            icon_url="https://x.com/pta.png",
            category="精密",
            tier="基石",
            description="用3次连续的普攻命中一名敌方英雄",
            source_url="https://www.ali213.net/zt/LOL/wiki/fw1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = rune_to_markdown(rune)
        assert "# 强攻" in md
        assert "**类别**: 精密" in md
        assert "**等级**: 基石" in md
        assert "用3次连续的普攻命中一名敌方英雄" in md


class TestWriteMarkdown:
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, "test.md")
            write_markdown("# Hello\n\nWorld", filepath)
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            assert content == "# Hello\n\nWorld"
