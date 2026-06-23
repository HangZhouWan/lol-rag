"""混合检索 + 两阶段精排 — 向量 + BM25 → RRF 融合 → Cross-Encoder 精排"""

from __future__ import annotations

import asyncio
import logging

from src.rag.models import RetrievedChunk

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion 常数
RRF_K = 60


class HybridRetriever:
    """混合检索器：并行向量检索和 BM25 检索，RRF 融合，Cross-Encoder 精排。"""

    def __init__(
        self,
        vector_store,       # VectorStoreManager
        embedder,           # Embedder
        bm25_index,         # BM25Index
        coarse_k: int = 10,
        rerank_k: int = 3,
        rerank_model: str = "BAAI/bge-reranker-base",
        min_relevance: float = 0,
    ):
        self._vector_store = vector_store
        self._embedder = embedder
        self._bm25_index = bm25_index
        self.coarse_k = coarse_k
        self.rerank_k = rerank_k
        self._rerank_model_name = rerank_model
        self._min_relevance = min_relevance
        self._cross_encoder = None  # 懒加载

    def _get_cross_encoder(self):
        """懒加载 Cross-Encoder 模型"""
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            logger.info("加载 Cross-Encoder 模型: %s", self._rerank_model_name)
            self._cross_encoder = CrossEncoder(self._rerank_model_name)
        return self._cross_encoder

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """完整检索流程：向量检索 + BM25 检索 → RRF 融合 → Cross-Encoder 精排。

        Returns:
            top-k RetrievedChunk 列表（按 rerank_score 降序）
        """
        if not query.strip():
            return []

        # 并行执行向量检索和 BM25 检索
        loop = asyncio.get_running_loop()
        vector_task = loop.run_in_executor(None, self._vector_search, query)
        bm25_task = loop.run_in_executor(None, self._bm25_search, query)

        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)

        # RRF 融合
        fused = self._rrf_fusion(vector_results, bm25_results)

        # 如果融合后结果少于 rerank_k，跳过精排
        if len(fused) <= self.rerank_k:
            logger.debug("融合后仅 %d 条结果 ≤ rerank_k=%d，跳过精排", len(fused), self.rerank_k)
            for c in fused:
                c.rerank_score = c.score  # 用融合分数代替
            return fused

        # Cross-Encoder 精排
        reranked = await loop.run_in_executor(None, self._rerank, query, fused)

        return reranked[: self.rerank_k]

    def _vector_search(self, query: str) -> list[RetrievedChunk]:
        """向量检索通路"""
        query_vec = self._embedder.embed_query(query)
        results = self._vector_store.similarity_search_with_score(
            query_vec, k=self.coarse_k
        )
        chunks = []
        for doc, score in results:
            chunks.append(
                RetrievedChunk(
                    content=doc.page_content,
                    metadata=dict(doc.metadata),
                    score=float(score),
                )
            )
        logger.debug("向量检索: %d 结果", len(chunks))
        return chunks

    def _bm25_search(self, query: str) -> list[RetrievedChunk]:
        """BM25 关键词检索通路"""
        results = self._bm25_index.search(query, k=self.coarse_k)
        chunks = []
        for doc, score in results:
            chunks.append(
                RetrievedChunk(
                    content=doc.page_content,
                    metadata=dict(doc.metadata),
                    score=float(score),
                )
            )
        logger.debug("BM25 检索: %d 结果", len(chunks))
        return chunks

    def _rrf_fusion(
        self,
        results_a: list[RetrievedChunk],
        results_b: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Reciprocal Rank Fusion：合并两路结果并去重。

        RRF_score(chunk) = Σ 1 / (RRF_K + rank_i)
        """
        # 用 metadata["source"] + content[前100] 做 dedup key
        def _key(chunk: RetrievedChunk) -> str:
            return f"{chunk.metadata.get('source', '')}|{chunk.metadata.get('section', '')}|{chunk.content[:80]}"

        # 收集所有唯一 chunk 及其在各通路中的 rank
        chunk_map: dict[str, RetrievedChunk] = {}
        ranks: dict[str, list[int]] = {}

        for rank_idx, chunk in enumerate(results_a, start=1):
            k = _key(chunk)
            chunk_map[k] = chunk
            ranks.setdefault(k, []).append(rank_idx)

        for rank_idx, chunk in enumerate(results_b, start=1):
            k = _key(chunk)
            if k not in chunk_map:
                chunk_map[k] = chunk
            ranks.setdefault(k, []).append(rank_idx)

        # 计算 RRF 分数
        scored: list[tuple[RetrievedChunk, float]] = []
        for k, chunk in chunk_map.items():
            rrf = sum(1.0 / (RRF_K + r) for r in ranks[k])
            scored.append((chunk, rrf))

        # 按 RRF 分数降序
        scored.sort(key=lambda x: x[1], reverse=True)

        # 取 top coarse_k
        top_chunks = []
        for chunk, rrf_score in scored[: self.coarse_k]:
            chunk.score = rrf_score  # 用 RRF 分数更新 score
            top_chunks.append(chunk)

        logger.debug("RRF 融合: %d 唯一结果 → top-%d", len(scored), len(top_chunks))
        return top_chunks

    def _rerank(
        self, query: str, chunks: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        """Cross-Encoder 精排（同步方法，由 run_in_executor 调用）"""
        ce = self._get_cross_encoder()

        pairs = [(query, chunk.content) for chunk in chunks]
        scores = ce.predict(pairs, show_progress_bar=False)

        # scores 可能是单值或列表
        if not hasattr(scores, "__len__"):
            scores = [scores]

        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)

        # 按精排分数降序
        chunks.sort(key=lambda c: c.rerank_score, reverse=True)

        logger.debug("精排完成: top-3 分数=%s",
                     [f"{c.rerank_score:.2f}" for c in chunks[:3]])
        return chunks
