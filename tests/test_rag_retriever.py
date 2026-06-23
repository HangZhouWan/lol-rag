# tests/test_rag_retriever.py
import shutil
import tempfile

import pytest

from langchain_core.documents import Document
from src.rag.models import RetrievedChunk


@pytest.fixture
def sample_chunks():
    return [
        Document(
            page_content="九尾妖狐阿狸是一位艾欧尼亚的法师英雄，她的Q技能是欺诈宝珠。",
            metadata={
                "source": "heroes/九尾妖狐.md",
                "category": "heroes",
                "name": "九尾妖狐",
                "section": "skill",
                "skill_key": "Q",
            },
        ),
        Document(
            page_content="阿狸的被动吸精之术在技能命中敌人时叠加精魄，叠满后下次技能附带治疗效果。",
            metadata={
                "source": "heroes/九尾妖狐.md",
                "category": "heroes",
                "name": "九尾妖狐",
                "section": "passive_skill",
            },
        ),
        Document(
            page_content="冰霜之心是一件传说级装备，售价2700金币，提供90护甲和20技能急速。",
            metadata={
                "source": "equipment/冰霜之心.md",
                "category": "equipment",
                "name": "冰霜之心",
                "section": "overview",
            },
        ),
        Document(
            page_content="冰霜之心的被动凛冬之拥使附近敌人攻速降低15%，所受普攻伤害至多降低40%。",
            metadata={
                "source": "equipment/冰霜之心.md",
                "category": "equipment",
                "name": "冰霜之心",
                "section": "effects",
            },
        ),
        Document(
            page_content="强攻是精密系的基石符文，第三次普攻造成额外适应伤害并使目标易损。",
            metadata={
                "source": "runes/强攻.md",
                "category": "runes",
                "name": "强攻",
                "section": "full",
            },
        ),
        Document(
            page_content="阿狸的R技能灵魂突袭可以进行最多三次冲刺，每次对附近敌人发射元气弹。",
            metadata={
                "source": "heroes/九尾妖狐.md",
                "category": "heroes",
                "name": "九尾妖狐",
                "section": "skill",
                "skill_key": "R",
            },
        ),
    ]


@pytest.fixture
def embedder():
    from src.rag.embedder import Embedder
    return Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")


@pytest.fixture
def temp_chroma_dir():
    tmpdir = tempfile.mkdtemp(prefix="retriever_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def hybrid_retriever(temp_chroma_dir, embedder, sample_chunks):
    from src.rag.vector_store import VectorStoreManager
    from src.rag.bm25_index import BM25Index
    from src.rag.retriever import HybridRetriever

    vs_mgr = VectorStoreManager(
        persist_dir=temp_chroma_dir,
        collection_name="test_retrieval",
        embedder=embedder,
    )
    vs_mgr.build_index(sample_chunks)

    bm25 = BM25Index()
    bm25.build(sample_chunks)

    return HybridRetriever(
        vector_store=vs_mgr,
        embedder=embedder,
        bm25_index=bm25,
        coarse_k=4,
        rerank_k=3,
    )


class TestHybridRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_equipment_query(self, hybrid_retriever):
        """查询装备相关问题，应返回装备相关 chunk"""
        results = await hybrid_retriever.retrieve("冰霜之心的被动是什么？")
        assert len(results) >= 1
        assert len(results) <= hybrid_retriever.rerank_k
        # 第一个结果应和冰霜之心相关
        assert any("冰霜" in c.content for c in results)

    @pytest.mark.asyncio
    async def test_retrieve_hero_query(self, hybrid_retriever):
        """查询英雄相关问题"""
        results = await hybrid_retriever.retrieve("阿狸的被动技能是什么？")
        assert len(results) >= 1
        # 应有阿狸的被动相关结果
        assert any("被动" in c.content or "吸精" in c.content for c in results)

    @pytest.mark.asyncio
    async def test_results_have_rerank_scores(self, hybrid_retriever):
        """精排后的 chunk 应有 rerank_score"""
        results = await hybrid_retriever.retrieve("冰霜之心")
        for chunk in results:
            assert chunk.rerank_score != 0.0

    @pytest.mark.asyncio
    async def test_empty_query_does_not_crash(self, hybrid_retriever):
        results = await hybrid_retriever.retrieve("")
        # 空查询不应崩溃，可能返回空列表或少数结果
        assert isinstance(results, list)


class TestVectorSearch:
    def test_vector_search_returns_scored_chunks(self, hybrid_retriever):
        results = hybrid_retriever._vector_search("阿狸")
        assert len(results) >= 1
        for r in results:
            assert r.score > 0


class TestBM25Search:
    def test_bm25_search_returns_scored_chunks(self, hybrid_retriever):
        results = hybrid_retriever._bm25_search("冰霜之心")
        assert len(results) >= 1
        for r in results:
            assert r.score > 0


class TestRRFFusion:
    def test_rrf_merges_and_dedupes(self, hybrid_retriever):
        # 模拟两路结果，有重叠
        chunk_a = RetrievedChunk(content="A", metadata={"source": "a.md"}, score=0.9)
        chunk_b = RetrievedChunk(content="B", metadata={"source": "b.md"}, score=0.8)
        chunk_c = RetrievedChunk(content="C", metadata={"source": "c.md"}, score=0.7)

        results_a = [chunk_a, chunk_b]
        results_b = [chunk_b, chunk_c]  # chunk_b 重叠

        fused = hybrid_retriever._rrf_fusion(results_a, results_b)
        # 应该去重
        sources = {c.metadata["source"] for c in fused}
        assert len(sources) == 3  # a, b, c
        assert len(fused) <= 3
