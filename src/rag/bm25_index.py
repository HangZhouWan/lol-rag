"""BM25 关键词索引 — 基于 jieba 分词的轻量 BM25 检索"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 索引的构建、查询与持久化。

    - 构建时对所有 chunk 内容做 jieba 分词后建立 BM25 索引
    - 分数归一化到 [0, 1]
    - 支持 pickle 序列化到磁盘
    """

    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._chunks: list[Document] = []
        self._tokenized_corpus: list[list[str]] = []

    def build(self, chunks: list[Document]) -> None:
        """对所有 chunk 分词后构建 BM25 索引"""
        self._chunks = list(chunks)
        self._tokenized_corpus = []
        for chunk in chunks:
            tokens = list(jieba.cut(chunk.page_content))
            # 过滤空白 token
            tokens = [t.strip() for t in tokens if t.strip()]
            self._tokenized_corpus.append(tokens)

        if self._tokenized_corpus:
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        else:
            self._bm25 = None
        logger.info("BM25 索引构建完成: %d 文档", len(chunks))

    def search(self, query: str, k: int = 10) -> list[tuple[Document, float]]:
        """检索并返回 (chunk, bm25_score) 列表，分数归一化到 [0, 1]。

        如果索引为空，返回空列表。
        """
        if self._bm25 is None or not self._chunks:
            return []

        query_tokens = list(jieba.cut(query))
        query_tokens = [t.strip() for t in query_tokens if t.strip()]

        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # 归一化到 [0, 1]：除以理论最大 BM25 分数
        max_score = scores.max()
        if max_score > 0:
            normalized = scores / max_score
        else:
            normalized = scores

        # 按分数降序取 top-k
        top_indices = normalized.argsort()[::-1][:k]

        results: list[tuple[Document, float]] = []
        for idx in top_indices:
            if normalized[idx] > 0:
                results.append((self._chunks[idx], float(normalized[idx])))

        return results

    def save(self, path: str) -> None:
        """序列化到磁盘（pickle 格式）"""
        data = {
            "chunks": self._chunks,
            "tokenized_corpus": self._tokenized_corpus,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("BM25 索引已保存: %s", path)

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        """从磁盘加载 BM25 索引"""
        with open(path, "rb") as f:
            data = pickle.load(f)

        index = cls()
        index._chunks = data["chunks"]
        index._tokenized_corpus = data["tokenized_corpus"]
        index._bm25 = BM25Okapi(index._tokenized_corpus)
        logger.info("BM25 索引已加载: %s (%d 文档)", path, len(index._chunks))
        return index
