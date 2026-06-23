# tests/test_rag_models.py
from src.rag.models import Message, RetrievedChunk, RAGResponse


def test_message_creation():
    msg = Message(role="user", content="冰霜之心的被动是什么？")
    assert msg.role == "user"
    assert msg.content == "冰霜之心的被动是什么？"
    assert msg.timestamp == ""  # 默认空


def test_message_with_timestamp():
    ts = "2026-06-22T10:30:00"
    msg = Message(role="assistant", content="你好", timestamp=ts)
    assert msg.timestamp == ts


def test_retrieved_chunk_defaults():
    chunk = RetrievedChunk(
        content="冰霜之心被动可使附近敌人攻速降低15%",
        metadata={"source": "data/equipment/冰霜之心.md", "category": "equipment"},
        score=0.85,
    )
    assert chunk.rerank_score == 0.0
    assert chunk.metadata["category"] == "equipment"


def test_retrieved_chunk_with_rerank():
    chunk = RetrievedChunk(
        content="some text",
        metadata={"source": "data/heroes/安妮.md"},
        score=0.65,
        rerank_score=8.3,
    )
    assert chunk.rerank_score == 8.3


def test_rag_response_fields():
    chunks = [
        RetrievedChunk(
            content="text1",
            metadata={"source": "data/heroes/a.md"},
            score=0.9,
            rerank_score=7.5,
        ),
        RetrievedChunk(
            content="text2",
            metadata={"source": "data/equipment/b.md"},
            score=0.8,
            rerank_score=6.0,
        ),
    ]
    resp = RAGResponse(
        answer="测试回答 [1]",
        citations=["data/heroes/a.md", "data/equipment/b.md"],
        chunks_used=chunks,
        generation_time_ms=3200,
        retrieval_time_ms=2300,
    )
    assert resp.answer == "测试回答 [1]"
    assert len(resp.citations) == 2
    assert len(resp.chunks_used) == 2
    assert resp.generation_time_ms == 3200
    assert resp.retrieval_time_ms == 2300
