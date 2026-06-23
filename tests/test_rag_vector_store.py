# tests/test_rag_vector_store.py
import shutil
import tempfile

import pytest

from langchain_core.documents import Document


@pytest.fixture
def sample_chunks():
    """创建测试用 chunk 列表"""
    return [
        Document(
            page_content="九尾妖狐阿狸是一位艾欧尼亚的法师，能够操控魔法能量摧毁敌人。",
            metadata={
                "source": "heroes/九尾妖狐.md",
                "category": "heroes",
                "name": "九尾妖狐",
                "section": "background",
            },
        ),
        Document(
            page_content="冰霜之心被动凛冬之拥使附近敌人攻速降低15%，普攻伤害至多降低40%。",
            metadata={
                "source": "equipment/冰霜之心.md",
                "category": "equipment",
                "name": "冰霜之心",
                "section": "effects",
            },
        ),
        Document(
            page_content="强攻符文对敌方英雄第三次连续普攻造成额外适应伤害。",
            metadata={
                "source": "runes/强攻.md",
                "category": "runes",
                "name": "强攻",
                "section": "full",
            },
        ),
    ]


@pytest.fixture
def temp_chroma_dir():
    """临时 ChromaDB 目录"""
    tmpdir = tempfile.mkdtemp(prefix="chroma_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def embedder():
    from src.rag.embedder import Embedder
    return Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")


class TestVectorStoreManager:
    def test_index_does_not_exist_initially(self, temp_chroma_dir, embedder):
        from src.rag.vector_store import VectorStoreManager
        mgr = VectorStoreManager(
            persist_dir=temp_chroma_dir,
            collection_name="test_collection",
            embedder=embedder,
        )
        assert mgr.index_exists() is False

    def test_build_index_and_check_exists(self, temp_chroma_dir, embedder, sample_chunks):
        from src.rag.vector_store import VectorStoreManager
        mgr = VectorStoreManager(
            persist_dir=temp_chroma_dir,
            collection_name="test_collection",
            embedder=embedder,
        )
        mgr.build_index(sample_chunks)
        assert mgr.index_exists() is True

    def test_retriever_returns_results(self, temp_chroma_dir, embedder, sample_chunks):
        from src.rag.vector_store import VectorStoreManager
        mgr = VectorStoreManager(
            persist_dir=temp_chroma_dir,
            collection_name="test_collection",
            embedder=embedder,
        )
        mgr.build_index(sample_chunks)

        retriever = mgr.as_retriever(top_k=2)
        results = retriever.invoke("冰霜之心的被动是什么")
        assert len(results) >= 1
        # 最高分结果应该与装备相关
        assert any("冰霜" in doc.page_content for doc in results)

    def test_rebuild_index_overwrites(self, temp_chroma_dir, embedder, sample_chunks):
        from src.rag.vector_store import VectorStoreManager
        mgr = VectorStoreManager(
            persist_dir=temp_chroma_dir,
            collection_name="test_collection",
            embedder=embedder,
        )
        mgr.build_index(sample_chunks)
        # 再次构建不应报错
        mgr.build_index(sample_chunks, force=True)
        assert mgr.index_exists() is True
