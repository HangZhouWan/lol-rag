# tests/test_rag_config.py
import os
import tempfile

import pytest


@pytest.fixture
def temp_env_file():
    """创建临时 .env 文件用于测试"""
    content = """
DEEPSEEK_API_KEY=sk-test-key-12345
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_MAX_TOKENS=2048
DEEPSEEK_TEMPERATURE=0.3
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_NORMALIZE=true
CHROMA_PERSIST_DIR=data/chroma_db
CHROMA_COLLECTION=lol-wiki
RETRIEVAL_TOP_K=10
RERANK_TOP_K=5
RERANK_MODEL=BAAI/bge-reranker-base
HYBRID_BM25_WEIGHT=0.3
MAX_HISTORY_TURNS=10
MAX_INPUT_LENGTH=2000
DATA_DIR=data
LOG_LEVEL=INFO
LOG_FILE=logs/rag.log
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        env_path = f.name
    yield env_path
    os.unlink(env_path)


def test_config_loads_all_values(temp_env_file, monkeypatch):
    """测试从 .env 加载所有配置项"""
    from src.rag.config import RAGConfig

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-12345")
    config = RAGConfig.from_env(temp_env_file)

    assert config.deepseek_api_key == "sk-test-key-12345"
    assert config.deepseek_model == "deepseek-chat"
    assert config.deepseek_max_tokens == 2048
    assert config.deepseek_temperature == 0.3
    assert config.embedding_model == "BAAI/bge-small-zh-v1.5"
    assert config.embedding_device == "cpu"
    assert config.embedding_normalize is True
    assert config.chroma_persist_dir == "data/chroma_db"
    assert config.chroma_collection == "lol-wiki"
    assert config.retrieval_top_k == 10
    assert config.rerank_top_k == 5
    assert config.rerank_model == "BAAI/bge-reranker-base"
    assert config.hybrid_bm25_weight == 0.3
    assert config.max_history_turns == 10
    assert config.max_input_length == 2000
    assert config.data_dir == "data"
    assert config.log_level == "INFO"
    assert config.log_file == "logs/rag.log"


def test_config_default_values():
    """测试 .env 缺失时使用默认值"""
    from src.rag.config import RAGConfig

    config = RAGConfig(deepseek_api_key="")

    assert config.deepseek_base_url == "https://api.deepseek.com"
    assert config.deepseek_model == "deepseek-chat"
    assert config.deepseek_max_tokens == 2048
    assert config.deepseek_temperature == 0.3
    assert config.embedding_model == "BAAI/bge-small-zh-v1.5"
    assert config.embedding_device == "cpu"
    assert config.retrieval_top_k == 10
    assert config.rerank_top_k == 5
    assert config.max_history_turns == 10
    assert config.max_input_length == 2000


def test_config_missing_api_key_raises():
    """测试 API key 缺失时抛出异常"""
    from src.rag.config import RAGConfig

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        RAGConfig(deepseek_api_key="").validate()


def test_config_from_env_file_not_found():
    """测试 .env 文件不存在时使用环境变量"""
    from src.rag.config import RAGConfig

    config = RAGConfig.from_env("/nonexistent/path/.env")
    # 应该不抛异常，使用环境变量或默认值
    assert config.deepseek_model == "deepseek-chat"
