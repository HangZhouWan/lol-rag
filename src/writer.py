"""Markdown 格式化与文件写入"""

import os
import re
import logging
from src.models import Hero, Equipment, Rune

logger = logging.getLogger(__name__)

# 文件名中不允许的字符
_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符。"""
    return _FILENAME_ILLEGAL.sub("", name).strip()


def hero_to_markdown(hero: Hero) -> str:
    """将 Hero 数据类格式化为 Markdown 字符串。"""
    lines = []
    lines.append(f"# {hero.name_cn} — {hero.name_en}")
    lines.append("")
    lines.append(f"*{hero.title}*")
    lines.append("")
    if hero.image_url:
        lines.append(f"![{hero.name_cn}]({hero.image_url})")
        lines.append("")
    if hero.role:
        lines.append(f"**定位**: {hero.role}")
        lines.append("")
    lines.append("---")
    lines.append("")

    if hero.background:
        lines.append("## 背景故事")
        lines.append("")
        lines.append(hero.background)
        lines.append("")

    if hero.initial_attrs or hero.max_attrs:
        lines.append("## 属性")
        lines.append("")
        lines.append("| 属性 | 初始值 | 满级值 |")
        lines.append("|------|--------|--------|")
        all_keys = set(hero.initial_attrs.keys()) | set(hero.max_attrs.keys())
        for key in sorted(all_keys):
            init = hero.initial_attrs.get(key, "—")
            maxv = hero.max_attrs.get(key, "—")
            lines.append(f"| {key} | {init} | {maxv} |")
        lines.append("")

    skills = []
    if hero.passive_skill:
        skills.append(("被动", hero.passive_skill))
    for i, s in enumerate(hero.skills):
        label = ["Q", "W", "E", "R"][i] if i < 4 else f"技能{i + 1}"
        skills.append((label, s))

    if skills:
        lines.append("## 技能")
        lines.append("")
        for label, s in skills:
            lines.append(f"### {label}：{s.name}")
            lines.append("")
            if s.icon_url:
                lines.append(f"![{s.name}]({s.icon_url})")
                lines.append("")
            if s.cost:
                lines.append(f"- **消耗**: {s.cost}")
            if s.cooldown:
                lines.append(f"- **冷却**: {s.cooldown}")
            if s.cast_range:
                lines.append(f"- **范围**: {s.cast_range}")
            if s.cost or s.cooldown or s.cast_range:
                lines.append("")
            lines.append(s.description)
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{hero.source_url}>  ")
    lines.append(f"> 抓取时间: {hero.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def equip_to_markdown(equip: Equipment) -> str:
    """将 Equipment 数据类格式化为 Markdown 字符串。"""
    lines = [f"# {equip.name}", ""]
    if equip.icon_url:
        lines.append(f"![{equip.name}]({equip.icon_url})")
        lines.append("")
    lines.append(f"**等级**: {equip.tier}")
    lines.append(f"**售价**: {equip.price}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if equip.base_attrs:
        lines.append("### 基础属性")
        lines.append("")
        for attr in equip.base_attrs:
            lines.append(f"- {attr}")
        lines.append("")

    if equip.active_effect:
        lines.append("### 主动效果")
        lines.append("")
        lines.append(equip.active_effect)
        lines.append("")

    if equip.passive_effect:
        lines.append("### 被动效果")
        lines.append("")
        lines.append(equip.passive_effect)
        lines.append("")

    if equip.mythic_bonus:
        lines.append("### 神话加成")
        lines.append("")
        lines.append(equip.mythic_bonus)
        lines.append("")

    if equip.recipe:
        lines.append("### 合成路线")
        lines.append("")
        for item in equip.recipe:
            lines.append(f"- {item}")
        lines.append("")

    if equip.recommended_heroes:
        lines.append("### 推荐英雄")
        lines.append("")
        lines.append("、".join(equip.recommended_heroes))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{equip.source_url}>  ")
    lines.append(f"> 抓取时间: {equip.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def rune_to_markdown(rune: Rune) -> str:
    """将 Rune 数据类格式化为 Markdown 字符串。"""
    lines = [f"# {rune.name}", ""]
    if rune.icon_url:
        lines.append(f"![{rune.name}]({rune.icon_url})")
        lines.append("")
    lines.append(f"**类别**: {rune.category}")
    lines.append(f"**等级**: {rune.tier}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 效果")
    lines.append("")
    lines.append(rune.description)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{rune.source_url}>  ")
    lines.append(f"> 抓取时间: {rune.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def write_markdown(content: str, filepath: str) -> None:
    """将 Markdown 内容写入文件。"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.debug(f"Written: {filepath}")
