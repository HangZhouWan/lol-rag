# tests/test_rag_chunker.py
from pathlib import Path

from langchain_core.documents import Document

from src.rag.chunker import chunk_documents, chunk_hero, chunk_equipment, chunk_rune


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "rag"


def _load_fixture(category: str, name: str) -> Document:
    path = FIXTURES_DIR / category / f"{name}.md"
    content = path.read_text(encoding="utf-8")
    return Document(
        page_content=content,
        metadata={
            "source": f"{category}/{name}.md",
            "category": category,
            "name": name,
        },
    )


class TestHeroChunking:
    def test_hero_produces_correct_chunk_count(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        # overview + background + attributes + skills = 4
        assert len(chunks) == 4, f"Expected 4 chunks, got {len(chunks)}"

    def test_hero_chunks_have_section_metadata(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        sections = {c.metadata.get("section") for c in chunks}
        assert "overview" in sections
        assert "skills" in sections, f"Expected 'skills' section, got: {sections}"

    def test_hero_chunks_preserve_source(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        for chunk in chunks:
            assert chunk.metadata["source"] == "heroes/九尾妖狐.md"
            assert chunk.metadata["category"] == "heroes"
            assert chunk.metadata["name"] == "九尾妖狐"

    def test_hero_passive_in_skills_chunk(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        skills_chunks = [
            c for c in chunks if c.metadata.get("section") == "skills"
        ]
        assert len(skills_chunks) == 1
        skills_content = skills_chunks[0].page_content
        assert "被动" in skills_content or "吸精" in skills_content
        # 确保所有 5 个技能都在同一个 chunk 中
        assert "Q" in skills_content or "欺诈宝珠" in skills_content
        assert "W" in skills_content or "妖狐业火" in skills_content
        assert "E" in skills_content or "魅惑妖术" in skills_content
        assert "R" in skills_content or "灵魂突袭" in skills_content

    def test_hero_skills_chunk_contains_all_skills(self):
        """验证技能 chunk 包含英雄的所有技能（被动+Q/W/E/R）"""
        doc = _load_fixture("heroes", "爆破鬼才")
        chunks = chunk_hero(doc)
        skills_chunks = [
            c for c in chunks if c.metadata.get("section") == "skills"
        ]
        assert len(skills_chunks) == 1, (
            f"Expected exactly 1 skills chunk, got {len(skills_chunks)}"
        )
        skills_content = skills_chunks[0].page_content
        # 验证所有 5 个技能都在同一个 chunk 中
        assert "一触即发" in skills_content, "Missing passive skill"
        assert "弹跳炸弹" in skills_content, "Missing Q skill"
        assert "定点爆破" in skills_content, "Missing W skill"
        assert "海克斯爆破雷区" in skills_content, "Missing E skill"
        assert "科学的地狱火炮" in skills_content, "Missing R skill"


class TestEquipmentChunking:
    def test_equipment_produces_correct_chunk_count(self):
        doc = _load_fixture("equipment", "冰霜之心")
        chunks = chunk_equipment(doc)
        assert 2 <= len(chunks) <= 3, f"Expected 2-3 chunks, got {len(chunks)}"

    def test_equipment_has_overview(self):
        doc = _load_fixture("equipment", "冰霜之心")
        chunks = chunk_equipment(doc)
        overview = [c for c in chunks if c.metadata.get("section") == "overview"]
        assert len(overview) == 1
        assert "冰霜之心" in overview[0].page_content
        assert "2700" in overview[0].page_content


class TestRuneChunking:
    def test_rune_returns_single_chunk(self):
        doc = _load_fixture("runes", "强攻")
        chunks = chunk_rune(doc)
        assert len(chunks) == 1
        assert chunks[0].metadata["section"] == "full"
        assert "强攻" in chunks[0].page_content


class TestChunkDocuments:
    def test_chunk_documents_dispatches_correctly(self):
        docs = [
            _load_fixture("heroes", "九尾妖狐"),
            _load_fixture("equipment", "冰霜之心"),
            _load_fixture("runes", "强攻"),
        ]
        all_chunks = chunk_documents(docs)
        assert len(all_chunks) >= (4 + 2 + 1)  # 英雄 4, 装备 ≥2, 符文 1

    def test_chunk_documents_handles_empty_list(self):
        chunks = chunk_documents([])
        assert chunks == []

    def test_chunk_metadata_has_all_required_fields(self):
        docs = [_load_fixture("heroes", "九尾妖狐")]
        chunks = chunk_documents(docs)
        for chunk in chunks:
            assert "source" in chunk.metadata
            assert "category" in chunk.metadata
            assert "name" in chunk.metadata
            assert "section" in chunk.metadata
