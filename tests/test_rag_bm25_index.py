# tests/test_rag_bm25_index.py
import os
import tempfile

import pytest

from langchain_core.documents import Document

from src.rag.bm25_index import BM25Index


@pytest.fixture
def sample_chunks():
    return [
        Document(
            page_content="九尾妖狐阿狸是一位艾欧尼亚的法师，能够操控魔法能量摧毁敌人。",
            metadata={"source": "heroes/九尾妖狐.md", "name": "九尾妖狐"},
        ),
        Document(
            page_content="冰霜之心被动凛冬之拥使附近敌人攻速降低15%。",
            metadata={"source": "equipment/冰霜之心.md", "name": "冰霜之心"},
        ),
        Document(
            page_content="强攻符文对敌方英雄第三次连续普攻造成额外适应伤害。",
            metadata={"source": "runes/强攻.md", "name": "强攻"},
        ),
        Document(
            page_content="阿狸的Q技能欺诈宝珠放出并收回宝珠，造成两段魔法伤害。",
            metadata={"source": "heroes/九尾妖狐.md", "name": "九尾妖狐"},
        ),
    ]


class TestBM25Index:
    def test_build_and_search(self, sample_chunks):
        index = BM25Index()
        index.build(sample_chunks)

        results = index.search("冰霜之心被动", k=2)
        assert len(results) >= 1
        top_chunk, top_score = results[0]
        assert "冰霜之心" in top_chunk.page_content

    def test_search_returns_scores_between_0_and_1(self, sample_chunks):
        index = BM25Index()
        index.build(sample_chunks)

        results = index.search("阿狸", k=3)
        for chunk, score in results:
            assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] range"

    def test_save_and_load(self, sample_chunks):
        index = BM25Index()
        index.build(sample_chunks)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            index.save(path)
            assert os.path.exists(path)

            loaded = BM25Index.load(path)
            results = loaded.search("强攻符文", k=2)
            assert len(results) >= 1
            assert any("强攻" in c.page_content for c, _ in results)
        finally:
            os.unlink(path)

    def test_empty_index_search(self):
        index = BM25Index()
        index.build([])
        results = index.search("anything", k=5)
        assert results == []

    def test_search_k_larger_than_corpus(self, sample_chunks):
        index = BM25Index()
        index.build(sample_chunks)

        results = index.search("阿狸", k=100)
        assert len(results) <= len(sample_chunks)
