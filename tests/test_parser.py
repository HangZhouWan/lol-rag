# tests/test_parser.py
import pytest
from src.scraper.parser import parse_hero_page, parse_equip_page, parse_rune_page
from src.scraper.models import Hero, Equipment, Rune

# ── Fixtures matching actual ali213.net block-based HTML structure ──────

HERO_HTML = """
<div class="listcontiner">
  <div class="main-container st0">
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st1" data-type="1" data-default="2">
        <span class="add-a">祖安怒兽</span>
      </div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st2" data-type="2">
        <img src="https://img.ali213.net/warwick.png" alt="" class="add-a">
      </div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st3" data-type="1" data-default="1">
        <span class="add-a">英雄背景故事</span>
      </div>
    </div>
    <div class="block-con can-add can-delete have-height"></div>
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st4" data-type="1" data-default="2">
        <span class="add-a">沃里克是祖安城中一个传奇人物，曾经是一名冷酷的赏金猎人...</span>
      </div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st5" data-type="1" data-default="1"><span class="add-a">名字</span></div>
      <div class="block-type can-change can-delete can-assign st6" data-type="1" data-default="2"><span class="add-a">沃里克</span></div>
      <div class="block-type can-change can-delete can-assign st5" data-type="1" data-default="1"><span class="add-a">定位</span></div>
      <div class="block-type can-change can-delete can-assign st6" data-type="1" data-default="2"><span class="add-a">战士</span></div>
    </div>
    <div class="block-con can-add can-delete have-height"></div>
    <div class="block-con can-add can-delete">
      <div class="block-type can-change can-delete can-assign st9" data-type="1" data-default="0"><span class="add-a">初始属性</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st5"><span class="add-a">攻击力</span></div><div class="block-type st6"><span class="add-a">65</span></div>
      <div class="block-type st5"><span class="add-a">攻击速度</span></div><div class="block-type st6"><span class="add-a">0.67</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st5"><span class="add-a">攻击距离</span></div><div class="block-type st6"><span class="add-a">125</span></div>
      <div class="block-type st5"><span class="add-a">移动速度</span></div><div class="block-type st6"><span class="add-a">335</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st5"><span class="add-a">生命值</span></div><div class="block-type st6"><span class="add-a">620</span></div>
      <div class="block-type st5"><span class="add-a">魔法值</span></div><div class="block-type st6"><span class="add-a">280</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st5"><span class="add-a">护甲值</span></div><div class="block-type st6"><span class="add-a">33</span></div>
      <div class="block-type st5"><span class="add-a">魔抗值</span></div><div class="block-type st6"><span class="add-a">32</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st9"><span class="add-a">满级属性</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st5"><span class="add-a">攻击力</span></div><div class="block-type st6"><span class="add-a">115</span></div>
      <div class="block-type st5"><span class="add-a">攻击速度</span></div><div class="block-type st6"><span class="add-a">1.05</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st9"><span class="add-a">被动技能</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st44" data-type="2">
        <img src="https://img.ali213.net/passive.png" alt="" class="add-a">
      </div>
      <div class="block-type st45" data-type="1" data-default="2"><span class="add-a">血之饥渴</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st4"><span class="add-a">沃里克的普通攻击造成额外魔法伤害。</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st9"><span class="add-a">Q技能</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st44" data-type="2">
        <img src="https://img.ali213.net/q.png" alt="" class="add-a">
      </div>
      <div class="block-type st45"><span class="add-a">野兽之口</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st50"><span class="add-a">技能消耗</span></div>
      <div class="block-type st51"><span class="add-a">50/60/70/80/90 法力</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st52"><span class="add-a">冷却时间</span></div>
      <div class="block-type st51"><span class="add-a">6秒</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st52"><span class="add-a">施法范围</span></div>
      <div class="block-type st51"><span class="add-a">350</span></div>
    </div>
    <div class="block-con can-add can-delete">
      <div class="block-type st4"><span class="add-a">沃里克向前猛扑...</span></div>
    </div>
  </div>
</div>
"""


class TestParseHeroPage:
    def test_parse_basic_hero(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero is not None
        assert isinstance(hero, Hero)
        assert hero.name_cn == "祖安怒兽"
        assert hero.name_en == "沃里克"
        assert hero.title == "祖安怒兽"
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
<div class="listcontiner">
  <div class="main-container">
    <div class="block-con">
      <div class="block-type st0" data-type="2">
        <img src="https://img.ali213.net/ice.png" alt="" class="add-a">
      </div>
    </div>
    <div class="block-con">
      <div class="block-type st1"><span class="add-a">冰霜之心</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st2"><span class="add-a">等级</span></div>
      <div class="block-type st3"><span class="add-a">传说</span></div>
      <div class="block-type st2"><span class="add-a">售价</span></div>
      <div class="block-type st3"><span class="add-a">2700</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st6"><span class="add-a">基础属性</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st7"><span class="add-a">+400 法力值，+20 技能急速，+50 护甲</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st6"><span class="add-a">被动效果</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st7"><span class="add-a">坚如磐石：使受到的伤害减少</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st6"><span class="add-a">合成路线</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st7"><span class="add-a">冰川圆盾+守望者铠甲+900 金币</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st6"><span class="add-a">推荐英雄</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st7"><span class="add-a">盖伦，德莱厄斯</span></div>
    </div>
  </div>
</div>
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
<div class="listcontiner">
  <div class="main-container st0">
    <div class="block-con">
      <div class="block-type st1" data-type="2">
        <img src="https://img.ali213.net/pta.png" alt="" class="add-a">
      </div>
      <div class="block-type st2" data-type="1" data-default="2"><span class="add-a">强攻</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st3"><span class="add-a">所属类别</span></div>
      <div class="block-type st4"><span class="add-a">精密</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st3"><span class="add-a">符文等级</span></div>
      <div class="block-type st4"><span class="add-a">基石</span></div>
    </div>
    <div class="block-con">
      <div class="block-type st7"><span class="add-a">用3次连续的普攻命中一名敌方英雄</span></div>
    </div>
  </div>
</div>
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
