"""Tests for URL builder module."""

import pytest
from src.url_builder import (
    build_hero_urls,
    build_equip_urls,
    build_rune_urls,
    build_all_urls,
    detect_category,
    get_category_dir,
)


class TestUrlBuilder:
    """URL builder tests."""

    def test_build_hero_urls(self):
        urls = build_hero_urls()
        assert len(urls) == 153
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/yx1.html"
        assert urls[-1] == "https://www.ali213.net/zt/LOL/wiki/yx153.html"

    def test_build_equip_urls(self):
        urls = build_equip_urls()
        assert len(urls) == 162
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/zb1.html"
        assert urls[-1] == "https://www.ali213.net/zt/LOL/wiki/zb162.html"

    def test_build_rune_urls(self):
        urls = build_rune_urls()
        assert len(urls) == 63
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/fw1.html"
        assert urls[-1] == "https://www.ali213.net/zt/LOL/wiki/fw63.html"

    def test_build_all_urls(self):
        hero, equip, rune = build_all_urls()
        assert len(hero) == 153
        assert len(equip) == 162
        assert len(rune) == 63

    def test_detect_category(self):
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/yx1.html") == "heroes"
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/zb99.html") == "equipment"
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/fw5.html") == "runes"

    def test_detect_category_unknown(self):
        with pytest.raises(ValueError, match="Unknown category"):
            detect_category("https://www.ali213.net/zt/LOL/wiki/other.html")

    def test_get_category_dir(self):
        assert get_category_dir("heroes") == "data/heroes"
        assert get_category_dir("equipment") == "data/equipment"
        assert get_category_dir("runes") == "data/runes"

    def test_get_category_dir_unknown(self):
        with pytest.raises(ValueError, match="Unknown category"):
            get_category_dir("unknown")
