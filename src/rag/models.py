"""RAG 系统数据模型"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Message:
    """单条对话消息"""
    role: str                      # "user" | "assistant"
    content: str
    timestamp: str = ""            # ISO 8601，由 conversation 模块填充


@dataclass
class RetrievedChunk:
    """检索结果"""
    content: str                   # 文本内容
    metadata: dict                 # source_file, category, section, name, ...
    score: float                   # 融合分数（RRF 后）
    rerank_score: float = 0.0      # 精排分数（粗筛阶段为 0）


@dataclass
class RAGResponse:
    """RAG 完整响应"""
    answer: str                    # 最终回答
    citations: list[str]           # 引用来源路径列表
    chunks_used: list[RetrievedChunk]  # 使用的检索结果
    generation_time_ms: int        # LLM 生成耗时（毫秒）
    retrieval_time_ms: int         # 检索耗时（毫秒）
