"""ChromaDB 向量存储管理 — 索引构建、持久化、查询"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """管理 ChromaDB 的索引构建、加载和查询。

    使用 LangChain 的 Chroma wrapper，支持自定义 embedding 函数。
    """

    def __init__(self, persist_dir: str, collection_name: str, embedder):
        """
        Args:
            persist_dir: ChromaDB 持久化目录
            collection_name: collection 名称
            embedder: Embedder 实例（需提供 embed_query 和 embed_documents 方法）
        """
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._embedder = embedder
        self._vector_store: Chroma | None = None

    def index_exists(self) -> bool:
        """检查 ChromaDB 索引是否已存在（持久化目录中是否有数据）"""
        persist_path = Path(self._persist_dir)
        if not persist_path.exists():
            return False
        # ChromaDB 使用 SQLite 存储，检查是否有 chroma.sqlite3 文件
        sqlite_file = persist_path / "chroma.sqlite3"
        return sqlite_file.exists() and sqlite_file.stat().st_size > 0

    def build_index(self, chunks: list[Document], force: bool = False) -> None:
        """构建（或重建）ChromaDB 索引。

        Args:
            chunks: 分块后的 Document 列表
            force: 是否强制重建（即使索引已存在）
        """
        if self.index_exists() and not force:
            logger.info("索引已存在，跳过构建。使用 --rebuild-index 强制重建。")
            return

        logger.info("开始构建向量索引: %d chunks → %s/%s",
                     len(chunks), self._persist_dir, self._collection_name)

        # 使用 LangChain Chroma wrapper 的 from_documents
        self._vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self._make_embedding_function(),
            persist_directory=self._persist_dir,
            collection_name=self._collection_name,
        )
        logger.info("向量索引构建完成: %d 文档已写入", len(chunks))

    def as_retriever(self, top_k: int = 10) -> BaseRetriever:
        """以 LangChain Retriever 形式返回向量检索器"""
        if self._vector_store is None:
            self._load()
        return self._vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k},
        )

    def similarity_search_with_score(
        self, query_embedding: list[float], k: int = 10
    ) -> list[tuple[Document, float]]:
        """使用预计算的 embedding 进行检索，返回 (Document, distance)"""
        if self._vector_store is None:
            self._load()
        return self._vector_store.similarity_search_by_vector_with_relevance_scores(
            embedding=query_embedding,
            k=k,
        )

    def _load(self) -> None:
        """从磁盘加载已有索引"""
        from langchain_chroma import Chroma

        self._vector_store = Chroma(
            persist_directory=self._persist_dir,
            collection_name=self._collection_name,
            embedding_function=self._make_embedding_function(),
        )

    def _make_embedding_function(self):
        """创建适配 LangChain Chroma 的 embedding 函数"""
        from langchain_core.embeddings import Embeddings

        embedder = self._embedder

        class _EmbeddingAdapter(Embeddings):
            def embed_documents(self_, texts: list[str]) -> list[list[float]]:
                return embedder.embed_documents(texts)

            def embed_query(self_, text: str) -> list[float]:
                return embedder.embed_query(text)

        return _EmbeddingAdapter()
