# tests/test_rag_cli.py
import subprocess
import sys


def test_cli_module_can_be_imported():
    """CLI 模块可导入"""
    from src.rag.cli import main
    assert callable(main)


def test_cli_help_flag():
    """--help 输出可用信息"""
    result = subprocess.run(
        [sys.executable, "-m", "src.rag.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "help" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_cli_rebuild_index_flag():
    """--rebuild-index 参数存在"""
    result = subprocess.run(
        [sys.executable, "-m", "src.rag.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "rebuild" in result.stdout.lower() or "rebuild-index" in result.stdout.lower()


class TestInputValidation:
    """测试输入验证逻辑（直接测试函数）"""

    def test_empty_input_returns_prompt(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("")
        assert is_valid is False
        assert "help" in msg.lower() or "输入" in msg

    def test_whitespace_only_returns_prompt(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("   \t  ")
        assert is_valid is False

    def test_help_command(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("/help")
        assert is_valid is False  # 非查询，是命令

    def test_clear_command(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("/clear")
        assert is_valid is False  # 非查询

    def test_quit_command(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("/quit")
        assert is_valid is False  # 非查询

    def test_exit_command(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("/exit")
        assert is_valid is False  # 非查询

    def test_normal_query_is_valid(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("冰霜之心的被动是什么？")
        assert is_valid is True
        assert msg == "冰霜之心的被动是什么？"

    def test_overly_long_input(self):
        from src.rag.cli import validate_input
        long_text = "测" * 2001
        is_valid, msg = validate_input(long_text)
        assert is_valid is False
        assert "过长" in msg or "2000" in msg

    def test_unknown_command(self):
        from src.rag.cli import validate_input
        is_valid, msg = validate_input("/unknown_command")
        assert is_valid is False
        assert "未知" in msg or "help" in msg.lower()


class TestOutputFormatting:
    def test_format_response(self):
        from src.rag.cli import format_response
        from src.rag.models import RAGResponse, RetrievedChunk

        chunks = [
            RetrievedChunk(
                content="test content",
                metadata={"source": "data/heroes/test.md"},
                score=0.9,
                rerank_score=7.5,
            ),
        ]
        resp = RAGResponse(
            answer="这是回答 [1]\n\n---\n[1] 来源: data/heroes/test.md",
            citations=["data/heroes/test.md"],
            chunks_used=chunks,
            generation_time_ms=3200,
            retrieval_time_ms=2300,
        )
        output = format_response(resp)
        assert "这是回答" in output
        assert "2300" in output or "2.3" in output  # 检索耗时
        assert "3200" in output or "3.2" in output     # 生成耗时
