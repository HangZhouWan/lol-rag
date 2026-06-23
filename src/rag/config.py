"""RAG 系统配置 — 从 .env 文件和环境变量加载"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RAGConfig:
    """RAG 系统所有配置项，带默认值"""

    deepseek_api_key: str

    # LLM
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_max_tokens: int = 2048
    deepseek_temperature: float = 0.3

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-1.5"
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # 向量存储
    chroma_persist_dir: str = "data/chroma_db"
    chroma_collection: str = "lol-wiki"

    # 检索
    retrieval_top_k: int = 10
    rerank_top_k: int = 3
    rerank_model: str = "BAAI/bge-reranker-base"
    hybrid_bm25_weight: float = 0.3

    # 对话
    max_history_turns: int = 10
    max_input_length: int = 2000

    # 数据
    data_dir: str = "data"

    # 日志
    log_level: str = "INFO"
    log_file: str = "logs/rag.log"

    @classmethod
    def from_env(cls, env_path: str | None = None) -> "RAGConfig":
        """从 .env 文件加载配置，缺失项使用默认值。

        加载顺序：先尝试 python-dotenv（如果文件存在），
        然后读取 os.environ，最后回退到默认值。
        """
        # 尝试加载 .env 文件
        if env_path is None:
            env_path = ".env"
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except (ImportError, FileNotFoundError):
            pass  # dotenv 不可用或文件不存在时静默跳过

        def _str(key: str, default: str) -> str:
            return os.environ.get(key, default)

        def _int(key: str, default: int) -> int:
            val = os.environ.get(key)
            return int(val) if val is not None else default

        def _float(key: str, default: float) -> float:
            val = os.environ.get(key)
            return float(val) if val is not None else default

        def _bool(key: str, default: bool) -> bool:
            val = os.environ.get(key)
            if val is None:
                return default
            return val.lower() in ("true", "1", "yes")

        return cls(
            deepseek_api_key=_str("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=_str("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_max_tokens=_int("DEEPSEEK_MAX_TOKENS", 2048),
            deepseek_temperature=_float("DEEPSEEK_TEMPERATURE", 0.3),
            embedding_model=_str("EMBEDDING_MODEL", "BAAI/bge-small-zh-1.5"),
            embedding_device=_str("EMBEDDING_DEVICE", "cpu"),
            embedding_normalize=_bool("EMBEDDING_NORMALIZE", True),
            chroma_persist_dir=_str("CHROMA_PERSIST_DIR", "data/chroma_db"),
            chroma_collection=_str("CHROMA_COLLECTION", "lol-wiki"),
            retrieval_top_k=_int("RETRIEVAL_TOP_K", 10),
            rerank_top_k=_int("RERANK_TOP_K", 3),
            rerank_model=_str("RERANK_MODEL", "BAAI/bge-reranker-base"),
            hybrid_bm25_weight=_float("HYBRID_BM25_WEIGHT", 0.3),
            max_history_turns=_int("MAX_HISTORY_TURNS", 10),
            max_input_length=_int("MAX_INPUT_LENGTH", 2000),
            data_dir=_str("DATA_DIR", "data"),
            log_level=_str("LOG_LEVEL", "INFO"),
            log_file=_str("LOG_FILE", "logs/rag.log"),
        )

    def validate(self) -> None:
        """校验必要配置项，不通过抛 ValueError"""
        if not self.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY 未设置。请在 .env 文件中配置或设置环境变量。"
            )
        if not Path(self.data_dir).exists():
            raise ValueError(
                f"DATA_DIR 路径不存在: {self.data_dir}"
            )
