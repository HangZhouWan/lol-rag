"""
集成测试 — 使用 mock LLM 测试完整 RAG pipeline 流程。

依赖 test fixtures (tests/fixtures/rag/) 中的示例数据。
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rag.config import RAGConfig
from src.rag.conversation import ConversationHistory


@pytest.fixture
def temp_dirs():
    """创建临时环境和数据目录"""
    base = tempfile.mkdtemp(prefix="rag_integration_")
    data_dir = Path(base) / "data"
    chroma_dir = Path(base) / "chroma_db"

    # 复制 fixture 数据
    fixtures = Path(__file__).parent / "fixtures" / "rag"
    shutil.copytree(fixtures, data_dir)

    yield {
        "data_dir": str(data_dir),
        "chroma_dir": str(chroma_dir),
    }
    shutil.rmtree(base, ignore_errors=True)


def make_config(temp_dirs) -> RAGConfig:
    return RAGConfig(
        deepseek_api_key="sk-test-integration",
        data_dir=temp_dirs["data_dir"],
        chroma_persist_dir=temp_dirs["chroma_dir"],
        chroma_collection="test_integration",
        retrieval_top_k=4,
        rerank_top_k=2,
        log_level="WARNING",
        log_file=str(Path(temp_dirs["chroma_dir"]).parent / "test.log"),
    )


class TestRAGIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock_llm(self, temp_dirs):
        """集成测试：加载 fixture 数据 → 构建索引 → 检索 → mock LLM 生成"""
        from src.rag import RAGPipeline

        config = make_config(temp_dirs)
        pipeline = RAGPipeline(config)
        await pipeline.initialize()

        history = ConversationHistory(max_turns=5)

        # Mock LLM 响应
        mock_answer = "冰霜之心的被动「凛冬之拥」使附近敌人攻速降低15% [1]\n\n---\n[1] 来源: equipment/冰霜之心.md"

        with patch.object(pipeline._generator, "agenerate", return_value=mock_answer) as mock_gen:
            response = await pipeline.query("冰霜之心的被动是什么？", history)

            assert response.answer == mock_answer
            assert response.retrieval_time_ms >= 0
            assert response.generation_time_ms >= 0
            assert len(response.chunks_used) > 0
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_hero_query(self, temp_dirs):
        """检索英雄相关内容"""
        from src.rag import RAGPipeline

        config = make_config(temp_dirs)
        pipeline = RAGPipeline(config)
        await pipeline.initialize()

        history = ConversationHistory(max_turns=5)

        mock_answer = "阿狸的被动是吸精之术 [1]"
        with patch.object(pipeline._generator, "agenerate", return_value=mock_answer):
            response = await pipeline.query("阿狸的被动技能是什么？", history)

            # 检索到的 chunk 应该包含阿狸的技能内容
            chunk_texts = " ".join(c.content for c in response.chunks_used)
            assert "九尾妖狐" in chunk_texts or "阿狸" in chunk_texts or "被动" in chunk_texts

    @pytest.mark.asyncio
    async def test_index_rebuild(self, temp_dirs):
        """测试索引重建不报错"""
        from src.rag import RAGPipeline

        config = make_config(temp_dirs)
        pipeline = RAGPipeline(config)
        await pipeline.initialize()

        # 强制重建
        await pipeline.rebuild_index()

        assert pipeline._vector_store.index_exists()

    @pytest.mark.asyncio
    async def test_conversation_history_flow(self, temp_dirs):
        """测试多轮对话流程"""
        from src.rag import RAGPipeline

        config = make_config(temp_dirs)
        pipeline = RAGPipeline(config)
        await pipeline.initialize()

        history = ConversationHistory(max_turns=5)

        mock_answer = "回答1"
        with patch.object(pipeline._generator, "agenerate", return_value=mock_answer):
            await pipeline.query("问题1", history)

        assert history.turn_count() == 1

        mock_answer2 = "回答2"
        with patch.object(pipeline._generator, "agenerate", return_value=mock_answer2):
            await pipeline.query("问题2", history)

        assert history.turn_count() == 2
        messages = history.get_history()
        assert len(messages) == 4  # 2 user + 2 assistant
