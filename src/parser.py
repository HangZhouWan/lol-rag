"""解析器模块：HTML 页面解析（暂存桩，等待实现）"""


def parse_hero_page(html: str, url: str, fetched_at: str):
    """Parse a hero detail page.

    Args:
        html: Raw HTML of the hero detail page.
        url: Source URL of the page.
        fetched_at: ISO-format timestamp of when the page was fetched.

    Returns:
        A Hero instance.

    Raises:
        NotImplementedError: The parser has not been implemented yet.
    """
    raise NotImplementedError("parse_hero_page not yet implemented")


def parse_equip_page(html: str, url: str, fetched_at: str):
    """Parse an equipment detail page.

    Args:
        html: Raw HTML of the equipment detail page.
        url: Source URL of the page.
        fetched_at: ISO-format timestamp of when the page was fetched.

    Returns:
        An Equipment instance.

    Raises:
        NotImplementedError: The parser has not been implemented yet.
    """
    raise NotImplementedError("parse_equip_page not yet implemented")


def parse_rune_page(html: str, url: str, fetched_at: str):
    """Parse a rune detail page.

    Args:
        html: Raw HTML of the rune detail page.
        url: Source URL of the page.
        fetched_at: ISO-format timestamp of when the page was fetched.

    Returns:
        A Rune instance.

    Raises:
        NotImplementedError: The parser has not been implemented yet.
    """
    raise NotImplementedError("parse_rune_page not yet implemented")
