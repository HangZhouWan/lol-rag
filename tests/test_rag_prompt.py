# tests/test_rag_prompt.py
from src.rag.models import RetrievedChunk, Message
from src.rag.prompt import SYSTEM_PROMPT, build_messages


def _make_chunk(content: str, source: str, index: int) -> RetrievedChunk:
    return RetrievedChunk(
        content=content,
        metadata={"source": source, "category": "heroes", "name": "Test"},
        score=0.9 - index * 0.1,
        rerank_score=8.0 - index,
    )


def test_system_prompt_contains_key_rules():
    assert "参考资料" in SYSTEM_PROMPT or "参考資料" in SYSTEM_PROMPT
    assert "编造" in SYSTEM_PROMPT
    assert "引用" in SYSTEM_PROMPT or "[N]" in SYSTEM_PROMPT
    assert "中文" in SYSTEM_PROMPT


def test_build_messages_includes_system_prompt():
    chunks = [_make_chunk("测试内容", "data/heroes/test.md", 0)]
    messages = build_messages(
        query="测试问题",
        chunks=chunks,
        history=[],
        system_prompt=SYSTEM_PROMPT,
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_build_messages_includes_context_with_citations():
    chunks = [
        _make_chunk("内容A", "data/heroes/a.md", 0),
        _make_chunk("内容B", "data/equipment/b.md", 1),
    ]
    messages = build_messages(
        query="问题",
        chunks=chunks,
        history=[],
        system_prompt=SYSTEM_PROMPT,
    )
    # 第二个 system 消息包含参考资料
    context_message = [m for m in messages if m["role"] == "system" and "## 参考资料" in m["content"]]
    assert len(context_message) == 1
    context = context_message[0]["content"]
    assert "[1]" in context
    assert "[2]" in context
    assert "data/heroes/a.md" in context
    assert "data/equipment/b.md" in context


def test_build_messages_includes_history():
    history = [
        Message(role="user", content="之前的问题"),
        Message(role="assistant", content="之前的回答"),
    ]
    chunks = [_make_chunk("内容", "data/test.md", 0)]
    messages = build_messages(
        query="新问题",
        chunks=chunks,
        history=history,
        system_prompt=SYSTEM_PROMPT,
    )
    roles = [m["role"] for m in messages]
    assert roles == ["system", "system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "新问题"


def test_build_messages_last_is_user_query():
    chunks = [_make_chunk("c", "s.md", 0)]
    messages = build_messages(
        query="最终问题",
        chunks=chunks,
        history=[],
        system_prompt=SYSTEM_PROMPT,
    )
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "最终问题"


def test_empty_chunks_produces_empty_context():
    messages = build_messages(
        query="问题",
        chunks=[],
        history=[],
        system_prompt=SYSTEM_PROMPT,
    )
    context_msg = [m for m in messages if "## 参考资料" in m.get("content", "")]
    assert len(context_msg) == 1
    assert context_msg[0]["content"].count("[1]") == 0
