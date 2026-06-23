"""HTML 解析器：从 Wiki 页面提取结构化数据

目标网站使用 CMS 区块系统（block-con > block-type.stN > span/img.add-a），
所有选择器均基于实际页面结构。
"""

import logging
import re
from bs4 import BeautifulSoup
from .models import Hero, Equipment, Rune, Skill

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────


def _st_class(bt) -> str | None:
    """Return the stN class from a block-type element, or None."""
    for c in bt.get("class", []):
        if re.match(r"^st\d+$", c):
            return c
    return None


def _extract_blocks(soup: BeautifulSoup) -> list[tuple[str | None, str, str]]:
    """Extract all block-type elements from the main container.

    Returns a list of (st_class, text, img_src) tuples.
    """
    container = soup.select_one(".main-container")
    if not container:
        return []

    blocks: list[tuple[str | None, str, str]] = []
    for block_con in container.find_all("div", class_="block-con"):
        for bt in block_con.find_all("div", class_="block-type"):
            st = _st_class(bt)
            span = bt.find("span", class_="add-a")
            img = bt.find("img", class_="add-a")
            text = span.get_text(strip=True) if span else ""
            img_src = img.get("src", "") if img else ""
            blocks.append((st, text, img_src))
    return blocks


def _text(el, default=""):
    """安全获取元素文本。"""
    return el.get_text(strip=True) if el else default


def _src(el, default=""):
    """安全获取元素 src 属性。"""
    return el.get("src", default) if el else default


# ── hero parser ────────────────────────────────────────────────────────


def parse_hero_page(html: str, url: str, fetched_at: str) -> Hero | None:
    """从英雄详情页 HTML 提取 Hero 数据。

    基于 ali213.net 的实际 CMS 区块结构解析。
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    blocks = _extract_blocks(soup)
    if not blocks:
        return None

    name_cn = ""
    name_en = ""
    image_url = ""
    role = ""
    background = ""
    initial_attrs: dict[str, str] = {}
    max_attrs: dict[str, str] = {}
    passive_skill: Skill | None = None
    skills: list[Skill] = []

    state = "pre"               # state machine: see _handle_st9
    pending_label: str | None = None   # st5 / st50 / st52 label
    # current-skill accumulators
    sk_name = ""
    sk_icon = ""
    sk_cost: str | None = None
    sk_cd: str | None = None
    sk_range: str | None = None

    def _flush_active_skill() -> None:
        """Build a Skill from accumulators and append to skills list."""
        nonlocal sk_name, sk_icon, sk_cost, sk_cd, sk_range
        if sk_name:
            skills.append(Skill(
                name=sk_name, icon_url=sk_icon,
                description="",  # filled by next st4
                cost=sk_cost, cooldown=sk_cd, cast_range=sk_range,
            ))
        # reset accumulators for next skill
        sk_name = ""
        sk_icon = ""
        sk_cost = None
        sk_cd = None
        sk_range = None

    for st, text, img_src in blocks:
        # ── st9: section headers — switch state ──
        if st == "st9":
            if text == "初始属性":
                state = "initial_attrs"
                pending_label = None
                continue
            if text == "满级属性":
                state = "max_attrs"
                pending_label = None
                continue
            if text == "被动技能":
                state = "passive"
                sk_name = ""
                sk_icon = ""
                continue
            if text in ("Q技能", "W技能", "E技能", "R技能"):
                state = "active_skill"
                sk_name = ""
                sk_icon = ""
                sk_cost = None
                sk_cd = None
                sk_range = None
                continue
            # unknown st9 — keep current state
            continue

        # ── st1: hero title (name_cn) ──
        if st == "st1" and state == "pre":
            name_cn = text
            continue

        # ── st2: hero image ──
        if st == "st2" and img_src and not image_url:
            image_url = img_src
            continue

        # ── st3: background section marker ──
        if st == "st3" and "背景" in text:
            state = "bg_pending"
            continue

        # ── st4: multi-purpose block (background / skill description) ──
        if st == "st4":
            if state == "bg_pending":
                background = text
                state = "name_role"
                pending_label = None
                continue
            if state == "passive":
                passive_skill = Skill(
                    name=sk_name, icon_url=sk_icon,
                    description=text,
                )
                state = "pre_skill"
                continue
            if state == "active_skill":
                # Description of the active skill just accumulated
                if skills:
                    skills[-1].description = text
                state = "pre_skill"
                continue
            continue

        # ── st5: label in a label/value pair ──
        if st == "st5":
            pending_label = text
            continue

        # ── st6: value in a label/value pair ──
        if st == "st6":
            if pending_label == "名字":
                name_en = text
            elif pending_label == "定位":
                role = text
            elif state == "initial_attrs" and pending_label:
                initial_attrs[pending_label] = text
            elif state == "max_attrs" and pending_label:
                max_attrs[pending_label] = text
            pending_label = None
            continue

        # ── st44: skill icon ──
        if st == "st44" and img_src:
            if state == "passive":
                sk_icon = img_src
            elif state == "active_skill":
                sk_icon = img_src
            continue

        # ── st45: skill name ──
        if st == "st45":
            if state == "passive":
                sk_name = text
            elif state == "active_skill":
                sk_name = text
            continue

        # ── st50 / st52: skill attribute label (消耗 / 冷却 / 范围) ──
        if st in ("st50", "st52"):
            pending_label = text
            continue

        # ── st51: skill attribute value ──
        if st == "st51":
            if pending_label is None:
                continue
            label = pending_label
            pending_label = None
            if state == "active_skill":
                if "消耗" in label:
                    sk_cost = text
                elif "冷却" in label:
                    sk_cd = text
                elif "范围" in label or "施法" in label:
                    sk_range = text
                # Apply to the partially built skill (last in skills if already flushed, or accumulate)
                # We accumulate and flush on st4 (description). But the skill object needs to exist.
                # Build the Skill object now if we have enough info, or defer.
                # We'll build a temporary entry; the description comes from the next st4.
                # Check if we already pushed a skill for this active_skill session
                if not skills or skills[-1].description:
                    # First set of details for this skill — create a placeholder
                    skills.append(Skill(
                        name=sk_name, icon_url=sk_icon,
                        description="",
                        cost=sk_cost, cooldown=sk_cd, cast_range=sk_range,
                    ))
                else:
                    # Update the existing placeholder
                    cur = skills[-1]
                    if sk_cost is not None:
                        cur.cost = sk_cost
                    if sk_cd is not None:
                        cur.cooldown = sk_cd
                    if sk_range is not None:
                        cur.cast_range = sk_range
                continue

    # ── fallback: try <title> tag for name_cn if not found ──
    if not name_cn:
        title_tag = soup.find("title")
        if title_tag:
            title_text = _text(title_tag)
            # "英雄联盟黑暗之女怎么样 ..." → extract hero title
            m = re.search(r"英雄联盟(.+?)怎么样", title_text)
            if m:
                name_cn = m.group(1)

    try:
        return Hero(
            name_cn=name_cn, name_en=name_en,
            title=name_cn,  # title = hero display name
            image_url=image_url, role=role, background=background,
            initial_attrs=initial_attrs, max_attrs=max_attrs,
            passive_skill=passive_skill, skills=skills,
            source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error constructing Hero for {url}: {e}")
        return None


# ── equipment parser ───────────────────────────────────────────────────


def parse_equip_page(html: str, url: str, fetched_at: str) -> Equipment | None:
    """从装备详情页 HTML 提取 Equipment 数据。

    基于 ali213.net 的实际 CMS 区块结构解析。
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    blocks = _extract_blocks(soup)
    if not blocks:
        return None

    name = ""
    icon_url = ""
    tier = ""
    price = ""
    base_attrs_text = ""
    active_effect: str | None = None
    passive_effect: str | None = None
    mythic_bonus: str | None = None
    recipe_text = ""
    recommended_heroes_text = ""

    current_section: str | None = None

    for st, text, img_src in blocks:
        # st0: equipment icon
        if st == "st0" and img_src:
            icon_url = img_src
            continue

        # st1: equipment name
        if st == "st1":
            name = text
            continue

        # st2: label (等级 / 售价)
        if st == "st2":
            current_section = text
            continue

        # st3: value for st2 label
        if st == "st3":
            if current_section == "等级":
                tier = text
            elif current_section == "售价":
                price = text
            current_section = None
            continue

        # st6: section header
        if st == "st6":
            current_section = text
            continue

        # st7: section content
        if st == "st7":
            content = text
            if current_section == "基础属性":
                base_attrs_text = content
            elif current_section == "主动效果":
                active_effect = content
            elif current_section == "被动效果":
                passive_effect = content
            elif current_section == "神话加成":
                mythic_bonus = content
            elif current_section == "合成路线":
                recipe_text = content
            elif current_section == "推荐英雄":
                recommended_heroes_text = content
            continue

    # Post-process: split base_attrs by Chinese comma or newline-like patterns
    base_attrs = [a.strip() for a in re.split(r"[，,、]", base_attrs_text) if a.strip()]
    recipe = [r.strip() for r in re.split(r"[+＋]", recipe_text) if r.strip()]
    recommended_heroes = [h.strip() for h in re.split(r"[，,、]", recommended_heroes_text) if h.strip()]

    try:
        return Equipment(
            name=name, icon_url=icon_url, tier=tier, price=price,
            base_attrs=base_attrs,
            active_effect=active_effect,
            passive_effect=passive_effect,
            mythic_bonus=mythic_bonus,
            recipe=recipe,
            recommended_heroes=recommended_heroes,
            source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error constructing Equipment for {url}: {e}")
        return None


# ── rune parser ────────────────────────────────────────────────────────


def parse_rune_page(html: str, url: str, fetched_at: str) -> Rune | None:
    """从符文详情页 HTML 提取 Rune 数据。

    基于 ali213.net 的实际 CMS 区块结构解析。
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    blocks = _extract_blocks(soup)
    if not blocks:
        return None

    name = ""
    icon_url = ""
    category = ""
    tier = ""
    description = ""

    pending_label: str | None = None

    for st, text, img_src in blocks:
        # st1: rune icon
        if st == "st1" and img_src:
            icon_url = img_src
            continue

        # st2: rune name
        if st == "st2":
            name = text
            continue

        # st3: label (所属类别 / 符文等级)
        if st == "st3":
            pending_label = text
            continue

        # st4: value for st3 label
        if st == "st4":
            if pending_label == "所属类别":
                category = text
            elif pending_label == "符文等级":
                tier = text
            pending_label = None
            continue

        # st7: rune description
        if st == "st7":
            description = text
            continue

    try:
        return Rune(
            name=name, icon_url=icon_url, category=category, tier=tier,
            description=description, source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error constructing Rune for {url}: {e}")
        return None
