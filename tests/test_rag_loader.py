# tests/test_rag_loader.py
from pathlib import Path

from src.rag.loader import load_documents


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "rag"


def test_load_documents_returns_list():
    docs = load_documents(str(FIXTURES_DIR))
    assert isinstance(docs, list)
    assert len(docs) >= 3  # 至少 3 个 test fixture 文件


def test_documents_have_metadata():
    docs = load_documents(str(FIXTURES_DIR))
    for doc in docs:
        assert "source" in doc.metadata, f"Missing 'source' in {doc.metadata}"
        assert "category" in doc.metadata, f"Missing 'category' in {doc.metadata}"
        assert "name" in doc.metadata, f"Missing 'name' in {doc.metadata}"


def test_documents_have_content():
    docs = load_documents(str(FIXTURES_DIR))
    for doc in docs:
        assert len(doc.page_content) > 0, f"Empty content for {doc.metadata['source']}"


def test_categories_are_correct():
    docs = load_documents(str(FIXTURES_DIR))
    categories = {doc.metadata["category"] for doc in docs}
    assert "heroes" in categories
    assert "equipment" in categories
    assert "runes" in categories


def test_hero_document_name():
    docs = load_documents(str(FIXTURES_DIR))
    hero_doc = next(d for d in docs if d.metadata["category"] == "heroes")
    assert hero_doc.metadata["name"] == "九尾妖狐"


def test_equipment_document_name():
    docs = load_documents(str(FIXTURES_DIR))
    equip_doc = next(d for d in docs if d.metadata["category"] == "equipment")
    assert equip_doc.metadata["name"] == "冰霜之心"


def test_empty_directory_returns_empty_list(tmp_path):
    empty_dir = tmp_path / "empty_data"
    empty_dir.mkdir()
    for sub in ("heroes", "equipment", "runes"):
        (empty_dir / sub).mkdir()
    docs = load_documents(str(empty_dir))
    assert docs == []


def test_missing_subdirectory_does_not_crash(tmp_path):
    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    (partial_dir / "heroes").mkdir()
    # equipment/ 和 runes/ 不存在 — 不应崩溃
    docs = load_documents(str(partial_dir))
    assert isinstance(docs, list)  # 空列表或只包含 heroes 下的文件
