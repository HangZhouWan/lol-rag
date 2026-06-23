"""URL construction and category detection utilities."""

import urllib.parse

from .config import (
    HERO_DETAIL_TMPL,
    EQUIP_DETAIL_TMPL,
    RUNE_DETAIL_TMPL,
    HERO_COUNT,
    EQUIP_COUNT,
    RUNE_COUNT,
    HERO_OUTPUT_DIR,
    EQUIP_OUTPUT_DIR,
    RUNE_OUTPUT_DIR,
)


def build_hero_urls() -> list[str]:
    """Build all hero detail page URLs."""
    return [HERO_DETAIL_TMPL.format(id=i) for i in range(1, HERO_COUNT + 1)]


def build_equip_urls() -> list[str]:
    """Build all equipment detail page URLs."""
    return [EQUIP_DETAIL_TMPL.format(id=i) for i in range(1, EQUIP_COUNT + 1)]


def build_rune_urls() -> list[str]:
    """Build all rune detail page URLs."""
    return [RUNE_DETAIL_TMPL.format(id=i) for i in range(1, RUNE_COUNT + 1)]


def build_all_urls() -> tuple[list[str], list[str], list[str]]:
    """Build all URLs for all categories.

    Returns:
        A tuple of (hero_urls, equip_urls, rune_urls).
    """
    return build_hero_urls(), build_equip_urls(), build_rune_urls()


def detect_category(url: str) -> str:
    """Detect the category of a URL based on its path pattern.

    Args:
        url: The URL to classify.

    Returns:
        One of "heroes", "equipment", or "runes".

    Raises:
        ValueError: If the URL does not match any known category.
    """
    # Parse the URL path and check the filename (last path segment)
    path = urllib.parse.urlparse(url).path
    filename = path.rstrip("/").split("/")[-1]
    if filename.startswith("yx"):
        return "heroes"
    if filename.startswith("zb"):
        return "equipment"
    if filename.startswith("fw"):
        return "runes"
    raise ValueError(f"Unknown category for URL: {url}")


def get_category_dir(category: str) -> str:
    """Get the output directory path for a given category.

    Args:
        category: One of "heroes", "equipment", or "runes".

    Returns:
        The corresponding output directory path.
    """
    mapping = {
        "heroes": HERO_OUTPUT_DIR,
        "equipment": EQUIP_OUTPUT_DIR,
        "runes": RUNE_OUTPUT_DIR,
    }
    value = mapping.get(category)
    if value is None:
        raise ValueError(f"Unknown category: {category}")
    return value
