"""数据模型定义"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    icon_url: str
    description: str
    cost: str | None = None
    cooldown: str | None = None
    cast_range: str | None = None


@dataclass
class Hero:
    name_cn: str
    name_en: str
    title: str
    image_url: str
    role: str
    background: str
    initial_attrs: dict[str, str]
    max_attrs: dict[str, str]
    passive_skill: Skill | None
    skills: list[Skill] = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class Equipment:
    name: str
    icon_url: str
    tier: str
    price: str
    base_attrs: list[str] = field(default_factory=list)
    active_effect: str | None = None
    passive_effect: str | None = None
    mythic_bonus: str | None = None
    recipe: list[str] = field(default_factory=list)
    recommended_heroes: list[str] = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class Rune:
    name: str
    icon_url: str
    category: str
    tier: str
    description: str
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class FetchRecord:
    url: str
    category: str
    name: str | None = None
    output_file: str | None = None
    fetched_at: str | None = None
    status: str = "pending"
    error: str | None = None
    retries: int = 0
    last_attempt: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "category": self.category,
            "name": self.name,
            "output_file": self.output_file,
            "fetched_at": self.fetched_at,
            "status": self.status,
            "error": self.error,
            "retries": self.retries,
            "last_attempt": self.last_attempt,
        }

    @classmethod
    def from_dict(cls, url: str, data: dict) -> "FetchRecord":
        # data may contain "url" from to_dict(); remove to avoid duplicate
        data.pop("url", None)
        return cls(url=url, **data)
