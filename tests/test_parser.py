# tests/test_parser.py
import pytest
from src.parser import parse_hero_page, parse_equip_page, parse_rune_page
from src.models import Hero, Equipment, Rune

HERO_HTML = """
<html><body>
<div class="detail-main">
  <h1>祖安怒兽 沃里克</h1>
  <img class="hero-img" src="https://img.ali213.net/warwick.png" />
  <div class="hero-info">
    <p class="name">沃里克</p>
    <p class="role">战士</p>
  </div>
  <div class="story">
    <p>沃里克是祖安城中一个传奇人物，曾经是一名冷酷的赏金猎人...</p>
  </div>
  <table class="attr-table" id="initial">
    <tr><th>攻击力</th><td>65</td></tr>
    <tr><th>攻击速度</th><td>0.67</td></tr>
    <tr><th>攻击距离</th><td>125</td></tr>
    <tr><th>移动速度</th><td>335</td></tr>
    <tr><th>生命值</th><td>620</td></tr>
    <tr><th>魔法值</th><td>280</td></tr>
    <tr><th>护甲值</th><td>33</td></tr>
    <tr><th>魔抗值</th><td>32</td></tr>
  </table>
  <table class="attr-table" id="max">
    <tr><th>攻击力</th><td>115</td></tr>
    <tr><th>攻击速度</th><td>1.05</td></tr>
  </table>
  <div class="skill passive">
    <img src="https://img.ali213.net/passive.png" />
    <h4>血之饥渴</h4>
    <p>沃里克的普通攻击造成额外魔法伤害。</p>
  </div>
  <div class="skill q">
    <img src="https://img.ali213.net/q.png" />
    <h4>野兽之口</h4>
    <p class="cost">消耗: 50/60/70/80/90 法力</p>
    <p class="cd">冷却: 6秒</p>
    <p class="range">范围: 350</p>
    <p>沃里克向前猛扑...</p>
  </div>
</div>
</body></html>
"""


class TestParseHeroPage:
    def test_parse_basic_hero(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero is not None
        assert isinstance(hero, Hero)
        assert hero.name_cn == "祖安怒兽"
        assert hero.name_en == "沃里克"
        assert hero.title == "祖安怒兽 沃里克"
        assert hero.role == "战士"
        assert "沃里克" in hero.background
        assert hero.image_url == "https://img.ali213.net/warwick.png"
        assert hero.fetched_at == "2026-06-18T10:00:00+08:00"

    def test_parse_attrs(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.initial_attrs.get("攻击力") == "65"
        assert hero.initial_attrs.get("移动速度") == "335"
        assert hero.max_attrs.get("攻击力") == "115"

    def test_parse_skills(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.passive_skill is not None
        assert hero.passive_skill.name == "血之饥渴"
        assert len(hero.skills) == 1
        assert hero.skills[0].name == "野兽之口"
        assert hero.skills[0].cost == "50/60/70/80/90 法力"
        assert hero.skills[0].cooldown == "6秒"
        assert hero.skills[0].cast_range == "350"

    def test_empty_html_returns_none(self):
        hero = parse_hero_page("", "http://test.com/yx1.html", "")
        assert hero is None

    def test_source_url_stored(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.source_url == "http://test.com/yx1.html"


EQUIP_HTML = """
<html><body>
<div class="detail-main">
  <h1>冰霜之心</h1>
  <img src="https://img.ali213.net/ice.png" />
  <p class="tier">传说</p>
  <p class="price">2700</p>
  <ul class="base-attrs">
    <li>+400 法力值</li>
    <li>+20 技能急速</li>
    <li>+50 护甲</li>
  </ul>
  <div class="passive"><p>坚如磐石：使受到的伤害减少</p></div>
  <div class="recipe">
    <li>冰川圆盾</li><li>守望者铠甲</li><li>900 金币</li>
  </div>
  <div class="rec-heroes"><li>盖伦</li><li>德莱厄斯</li></div>
</div>
</body></html>
"""


class TestParseEquipPage:
    def test_parse_basic_equip(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert equip is not None
        assert equip.name == "冰霜之心"
        assert equip.icon_url == "https://img.ali213.net/ice.png"
        assert equip.tier == "传说"
        assert equip.price == "2700"
        assert len(equip.base_attrs) == 3
        assert "+400 法力值" in equip.base_attrs
        assert equip.source_url == "http://test.com/zb1.html"
        assert equip.fetched_at == "2026-06-18T10:00:00+08:00"

    def test_parse_passive(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert equip.passive_effect is not None
        assert "坚如磐石" in equip.passive_effect

    def test_parse_recipe(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert len(equip.recipe) == 3
        assert "冰川圆盾" in equip.recipe

    def test_parse_rec_heroes(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert len(equip.recommended_heroes) == 2
        assert "盖伦" in equip.recommended_heroes

    def test_equip_no_active_or_mythic(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert equip is not None
        assert equip.active_effect is None
        assert equip.mythic_bonus is None


RUNE_HTML = """
<html><body>
<div class="detail-main">
  <h1>强攻</h1>
  <img src="https://img.ali213.net/pta.png" />
  <p class="category">精密</p>
  <p class="tier">基石</p>
  <div class="desc"><p>用3次连续的普攻命中一名敌方英雄</p></div>
</div>
</body></html>
"""


class TestParseRunePage:
    def test_parse_basic_rune(self):
        rune = parse_rune_page(RUNE_HTML, "http://test.com/fw1.html", "2026-06-18T10:00:00+08:00")
        assert rune is not None
        assert rune.name == "强攻"
        assert rune.icon_url == "https://img.ali213.net/pta.png"
        assert rune.category == "精密"
        assert rune.tier == "基石"
        assert "普攻" in rune.description
        assert rune.source_url == "http://test.com/fw1.html"
        assert rune.fetched_at == "2026-06-18T10:00:00+08:00"
