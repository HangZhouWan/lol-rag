"""BGE Embedding 包装器 — 封装 sentence-transformers 模型"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# BGE 模型要求的 query 前缀（嵌入时需要加在 query 之前）
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class Embedder:
    """sentence-transformers 的薄封装。

    模型在首次使用时懒加载（进程级单例模式可通过外部管理）。
    每次创建 Embedder 实例时加载一次模型。
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
        normalize: bool = True,
    ):
        self._model_name = model_name
        self._device = device
        self._normalize = normalize

        from sentence_transformers import SentenceTransformer

        logger.info("加载 embedding 模型: %s (device=%s)", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._dimension: int = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        """返回 embedding 向量维度"""
        return self._dimension

    def embed_query(self, query: str) -> list[float]:
        """为检索查询生成 embedding。BGE 模型自动加 query 前缀。"""
        prefixed = BGE_QUERY_PREFIX + query
        vec = self._model.encode(
            prefixed,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """为文档内容批量生成 embedding。不加 query 前缀。"""
        if not texts:
            return []
        vecs = self._model.encode(
            texts,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecs]
