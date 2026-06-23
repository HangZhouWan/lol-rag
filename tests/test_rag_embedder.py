# tests/test_rag_embedder.py
import numpy as np


class TestEmbedder:
    def test_embed_query_returns_list_of_floats(self):
        """测试 query embedding 返回 float 列表"""
        from src.rag.embedder import Embedder

        embedder = Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")
        vec = embedder.embed_query("测试问题")
        assert isinstance(vec, list)
        assert len(vec) > 0
        assert all(isinstance(v, float) for v in vec)

    def test_embed_documents_returns_list_of_lists(self):
        """测试批量文档 embedding"""
        from src.rag.embedder import Embedder

        embedder = Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")
        texts = ["文档内容A", "文档内容B", "文档内容C"]
        vecs = embedder.embed_documents(texts)
        assert isinstance(vecs, list)
        assert len(vecs) == 3
        for vec in vecs:
            assert isinstance(vec, list)
            assert all(isinstance(v, float) for v in vec)

    def test_dimension_matches(self):
        """测试维度属性返回正确的值"""
        from src.rag.embedder import Embedder

        embedder = Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")
        dim = embedder.dimension
        assert isinstance(dim, int)
        assert dim == 512  # bge-small-zh-1.5 维度

    def test_normalize_produces_unit_vectors(self):
        """测试归一化后向量模长为 1"""
        from src.rag.embedder import Embedder

        embedder = Embedder(
            model_name="BAAI/bge-small-zh-v1.5", device="cpu", normalize=True
        )
        vec = embedder.embed_query("测试")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-4

    def test_query_prefix_is_different_from_doc(self):
        """测试 query embedding 和文档 embedding 对相同文本产生不同向量（BGE 前缀效果）"""
        from src.rag.embedder import Embedder

        embedder = Embedder(model_name="BAAI/bge-small-zh-v1.5", device="cpu")
        text = "冰霜之心"
        query_vec = embedder.embed_query(text)    # 带 query 前缀
        doc_vecs = embedder.embed_documents([text])  # 不带前缀
        # 两者不应完全相同（因为有 query 前缀）
        assert query_vec != doc_vecs[0]
