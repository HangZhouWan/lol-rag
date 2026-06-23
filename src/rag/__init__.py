"""英雄联盟 RAG 系统 — Pipeline 总编排

RAGPipeline 负责：
1. 首次启动时自动构建索引（或加载已有索引）
2. 处理每次查询的完整流程：检索 → prompt 构建 → LLM 生成 → 响应
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from src.rag.config import RAGConfig
from src.rag.models import RAGResponse
from src.rag.loader import load_documents
from src.rag.chunker import chunk_documents
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStoreManager
from src.rag.bm25_index import BM25Index
from src.rag.retriever import HybridRetriever
from src.rag.generator import Generator
from src.rag.prompt import build_messages, SYSTEM_PROMPT
from src.rag.conversation import ConversationHistory

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG 系统总编排器，串联所有模块。"""

    def __init__(self, config: RAGConfig):
        self._config = config
        self._embedder: Embedder | None = None
        self._vector_store: VectorStoreManager | None = None
        self._bm25_index: BM25Index | None = None
        self._retriever: HybridRetriever | None = None
        self._generator: Generator | None = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """初始化所有子模块。首启动自动构建索引。"""
        logger.info("初始化 RAG Pipeline...")

        # 1. Embedder
        self._embedder = Embedder(
            model_name=self._config.embedding_model,
            device=self._config.embedding_device,
            normalize=self._config.embedding_normalize,
        )

        # 2. Vector Store
        self._vector_store = VectorStoreManager(
            persist_dir=self._config.chroma_persist_dir,
            collection_name=self._config.chroma_collection,
            embedder=self._embedder,
        )

        # 3. BM25 Index
        bm25_path = Path(self._config.chroma_persist_dir) / "bm25_index.pkl"
        self._bm25_index = BM25Index()

        # 4. 检查/构建索引
        if not self._vector_store.index_exists():
            logger.info("索引不存在，开始自动构建...")
            await self._build_index()
        else:
            logger.info("加载已有索引...")
            # BM25 从持久化路径加载
            if bm25_path.exists():
                try:
                    self._bm25_index = BM25Index.load(str(bm25_path))
                except Exception:
                    logger.warning("BM25 索引加载失败，将重建", exc_info=True)
                    await self._rebuild_bm25()
            else:
                await self._rebuild_bm25()

        # 5. Retriever
        self._retriever = HybridRetriever(
            vector_store=self._vector_store,
            embedder=self._embedder,
            bm25_index=self._bm25_index,
            coarse_k=self._config.retrieval_top_k,
            rerank_k=self._config.rerank_top_k,
            rerank_model=self._config.rerank_model,
        )

        # 6. Generator
        self._generator = Generator(
            api_key=self._config.deepseek_api_key,
            base_url=self._config.deepseek_base_url,
            model=self._config.deepseek_model,
            max_tokens=self._config.deepseek_max_tokens,
            temperature=self._config.deepseek_temperature,
        )

        self._initialized = True
        logger.info("RAG Pipeline 初始化完成")

    async def _build_index(self) -> None:
        """构建完整索引：加载文档 → 分块 → 向量索引 + BM25 索引"""
        logger.info("加载文档: %s", self._config.data_dir)
        docs = load_documents(self._config.data_dir)
        logger.info("已加载 %d 个文档", len(docs))

        chunks = chunk_documents(docs)
        logger.info("已分块: %d chunks", len(chunks))

        # 构建向量索引
        self._vector_store.build_index(chunks)

        # 构建 BM25 索引
        self._bm25_index.build(chunks)
        bm25_path = Path(self._config.chroma_persist_dir) / "bm25_index.pkl"
        self._bm25_index.save(str(bm25_path))

    async def _rebuild_bm25(self) -> None:
        """仅重建 BM25 索引（从已加载的文档）"""
        docs = load_documents(self._config.data_dir)
        chunks = chunk_documents(docs)
        self._bm25_index.build(chunks)
        bm25_path = Path(self._config.chroma_persist_dir) / "bm25_index.pkl"
        self._bm25_index.save(str(bm25_path))

    async def rebuild_index(self) -> None:
        """强制重建索引"""
        logger.info("强制重建索引...")
        docs = load_documents(self._config.data_dir)
        chunks = chunk_documents(docs)
        self._vector_store.build_index(chunks, force=True)
        self._bm25_index.build(chunks)
        bm25_path = Path(self._config.chroma_persist_dir) / "bm25_index.pkl"
        self._bm25_index.save(str(bm25_path))
        # 重建后需要重建 retriever
        self._retriever = HybridRetriever(
            vector_store=self._vector_store,
            embedder=self._embedder,
            bm25_index=self._bm25_index,
            coarse_k=self._config.retrieval_top_k,
            rerank_k=self._config.rerank_top_k,
            rerank_model=self._config.rerank_model,
        )

    async def query(
        self, question: str, history: ConversationHistory
    ) -> RAGResponse:
        """处理单次 RAG 查询的完整流程。

        Args:
            question: 用户问题
            history: 对话历史对象

        Returns:
            RAGResponse 包含回答、引用、耗时等信息
        """
        if not self._initialized:
            await self.initialize()

        # 1. 检索
        t0 = time.perf_counter()
        chunks = await self._retriever.retrieve(question)
        retrieval_time_ms = int((time.perf_counter() - t0) * 1000)

        # 2. 构建 prompt
        history_msgs = history.get_history()
        messages = build_messages(
            query=question,
            chunks=chunks,
            history=history_msgs,
            system_prompt=SYSTEM_PROMPT,
        )

        # 3. LLM 生成
        t1 = time.perf_counter()
        try:
            answer = await self._generator.agenerate(messages)
        except Exception:
            logger.error("LLM 调用失败", exc_info=True)
            answer = "服务暂时不可用，请稍后重试。"
        generation_time_ms = int((time.perf_counter() - t1) * 1000)

        # 4. 提取引用
        citations = [chunk.metadata["source"] for chunk in chunks]

        # 5. 日志
        total_ms = retrieval_time_ms + generation_time_ms
        hit = len(chunks) > 0
        logger.info(
            "query=%r retrieval_ms=%d generation_ms=%d total_ms=%d chunks=%d hit=%s",
            question[:100], retrieval_time_ms, generation_time_ms, total_ms,
            len(chunks), str(hit).lower(),
        )

        return RAGResponse(
            answer=answer,
            citations=citations,
            chunks_used=chunks,
            generation_time_ms=generation_time_ms,
            retrieval_time_ms=retrieval_time_ms,
        )

    @property
    def stats(self) -> dict:
        """返回当前系统状态"""
        return {
            "initialized": self._initialized,
            "embedding_model": self._config.embedding_model,
            "embedding_dim": self._embedder.dimension if self._embedder else None,
            "index_exists": self._vector_store.index_exists() if self._vector_store else False,
        }
