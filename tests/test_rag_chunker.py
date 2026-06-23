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
        assert len(chunks) >= 5, f"Expected >=5 chunks, got {len(chunks)}"

    def test_hero_chunks_have_section_metadata(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        sections = {c.metadata.get("section") for c in chunks}
        assert "overview" in sections
        assert "skill" in sections or "passive_skill" in sections

    def test_hero_chunks_preserve_source(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        for chunk in chunks:
            assert chunk.metadata["source"] == "heroes/九尾妖狐.md"
            assert chunk.metadata["category"] == "heroes"
            assert chunk.metadata["name"] == "九尾妖狐"

    def test_hero_passive_identified(self):
        doc = _load_fixture("heroes", "九尾妖狐")
        chunks = chunk_hero(doc)
        passive_chunks = [
            c for c in chunks if c.metadata.get("section") == "passive_skill"
        ]
        assert len(passive_chunks) >= 1
        assert "被动" in passive_chunks[0].page_content or "吸精" in passive_chunks[0].page_content


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
        assert len(all_chunks) >= (5 + 2 + 1)  # 英雄 ≥5, 装备 ≥2, 符文 1

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
