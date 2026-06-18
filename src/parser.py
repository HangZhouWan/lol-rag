"""HTML 解析器：从 Wiki 页面提取结构化数据

注意：CSS 选择器需要根据目标网站的实际 HTML 结构调整。
当前选择器基于常见 Wiki 布局模式。
"""

import logging
from bs4 import BeautifulSoup
from src.models import Hero, Equipment, Rune, Skill

logger = logging.getLogger(__name__)


def _text(el, default=""):
    """安全获取元素文本。"""
    return el.get_text(strip=True) if el else default


def _src(el, default=""):
    """安全获取元素 src 属性。"""
    return el.get("src", default) if el else default


def _strip_label(text: str) -> str:
    """移除标签前缀（如 消耗:、冷却:、范围:），仅保留值部分。"""
    if ":" in text:
        parts = text.split(":", 1)
        return parts[1].strip()
    return text


def _parse_table_to_dict(table) -> dict[str, str]:
    """将 HTML <table> 解析为 {key: value} 字典。"""
    result = {}
    if not table:
        return result
    for row in table.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            result[_text(th)] = _text(td)
    return result


def parse_hero_page(html: str, url: str, fetched_at: str) -> Hero | None:
    """从英雄详情页 HTML 提取 Hero 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        h1 = soup.find("h1")
        title_text = _text(h1).strip()
        parts = title_text.rsplit(" ", 1)
        if len(parts) == 2:
            name_cn = parts[0]
            name_en = parts[1]
        else:
            name_cn = title_text
            name_en = ""
            logger.warning("Missing name_en for title: %s", title_text)

        img = soup.select_one("img.hero-img, .detail-main img:first-of-type")
        image_url = _src(img)

        role_el = soup.select_one(".role, [class*='role']")
        role = _text(role_el)

        story_el = soup.select_one(".story, [class*='story'], .background")
        background = _text(story_el)

        initial_table = soup.select_one("#initial, .initial-attrs, table:first-of-type")
        initial_attrs = _parse_table_to_dict(initial_table)

        max_table = soup.select_one("#max, .max-attrs, table:nth-of-type(2)")
        max_attrs = _parse_table_to_dict(max_table)

        passive_skill = None
        skills = []

        skill_divs = soup.select(".skill, [class*='skill-item'], .ability")
        for div in skill_divs:
            classes = div.get("class", [])
            is_passive = any("passive" in c.lower() for c in classes)

            s_name = _text(div.find("h4") or div.find("h3") or div.find("strong"))
            s_icon = _src(div.find("img"))
            s_desc = _text(div.select_one("p:last-of-type") or div.select_one(".desc"))
            s_cost = _strip_label(_text(div.select_one(".cost, [class*='cost']"))) or None
            s_cd = _strip_label(_text(div.select_one(".cd, [class*='cd'], [class*='cooldown']"))) or None
            s_range = _strip_label(_text(div.select_one(".range, [class*='range']"))) or None

            skill = Skill(
                name=s_name, icon_url=s_icon, description=s_desc,
                cost=s_cost, cooldown=s_cd, cast_range=s_range,
            )
            if is_passive:
                passive_skill = skill
            else:
                skills.append(skill)

        return Hero(
            name_cn=name_cn, name_en=name_en, title=title_text,
            image_url=image_url, role=role, background=background,
            initial_attrs=initial_attrs, max_attrs=max_attrs,
            passive_skill=passive_skill, skills=skills,
            source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error parsing hero page {url}: {e}")
        return None


def parse_equip_page(html: str, url: str, fetched_at: str) -> Equipment | None:
    """从装备详情页 HTML 提取 Equipment 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        name = _text(soup.find("h1")).strip()
        icon_url = _src(soup.select_one("img:first-of-type"))
        tier = _text(soup.select_one(".tier, [class*='tier']"))
        price = _text(soup.select_one(".price, [class*='price']"))

        base_attrs_el = soup.select(".base-attrs li, [class*='base'] li, .attrs li")
        base_attrs = [_text(li) for li in base_attrs_el if _text(li)]

        active_el = soup.select_one(".active, [class*='active']")
        active_effect = _text(active_el) or None
        passive_el = soup.select_one(".passive, [class*='passive']")
        passive_effect = _text(passive_el) or None

        mythic_el = soup.select_one(".mythic, [class*='mythic']")
        mythic_bonus = _text(mythic_el) or None

        recipe_els = soup.select(".recipe li, [class*='recipe'] li")
        recipe = [_text(r) for r in recipe_els if _text(r)]

        hero_els = soup.select(".rec-heroes li, [class*='hero'] li, .recommend li")
        recommended_heroes = [_text(h) for h in hero_els if _text(h)]

        return Equipment(
            name=name, icon_url=icon_url, tier=tier, price=price,
            base_attrs=base_attrs, active_effect=active_effect,
            passive_effect=passive_effect, mythic_bonus=mythic_bonus,
            recipe=recipe, recommended_heroes=recommended_heroes,
            source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error parsing equipment page {url}: {e}")
        return None


def parse_rune_page(html: str, url: str, fetched_at: str) -> Rune | None:
    """从符文详情页 HTML 提取 Rune 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        name = _text(soup.find("h1")).strip()
        icon_url = _src(soup.select_one("img:first-of-type"))
        category = _text(soup.select_one(".category, [class*='category']"))
        tier = _text(soup.select_one(".tier, [class*='tier']"))
        description = _text(soup.select_one(".desc, [class*='desc'], .effect"))

        return Rune(
            name=name, icon_url=icon_url, category=category, tier=tier,
            description=description, source_url=url, fetched_at=fetched_at,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.error(f"Error parsing rune page {url}: {e}")
        return None
