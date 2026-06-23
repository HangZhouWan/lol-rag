# tests/test_rag_conversation.py
from src.rag.conversation import ConversationHistory


class TestConversationHistory:
    def test_add_and_get_messages(self):
        hist = ConversationHistory(max_turns=10)
        hist.add_user_message("问题1")
        hist.add_assistant_message("回答1")

        messages = hist.get_history()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "问题1"
        assert messages[1].role == "assistant"
        assert messages[1].content == "回答1"

    def test_turn_count(self):
        hist = ConversationHistory(max_turns=10)
        assert hist.turn_count() == 0

        hist.add_user_message("q1")
        assert hist.turn_count() == 0  # 未完成一轮

        hist.add_assistant_message("a1")
        assert hist.turn_count() == 1  # 完成一轮

    def test_clear_history(self):
        hist = ConversationHistory(max_turns=10)
        hist.add_user_message("q1")
        hist.add_assistant_message("a1")
        hist.clear()
        assert hist.get_history() == []
        assert hist.turn_count() == 0

    def test_max_turns_truncation(self):
        hist = ConversationHistory(max_turns=2)
        # 添加 3 轮对话
        for i in range(3):
            hist.add_user_message(f"q{i}")
            hist.add_assistant_message(f"a{i}")

        messages = hist.get_history()
        # 应保留最近 2 轮 = 4 条消息
        assert len(messages) == 4
        # 最早的消息应该是 q1（不是 q0）
        assert messages[0].content == "q1"
        assert messages[-1].content == "a2"

    def test_is_full(self):
        hist = ConversationHistory(max_turns=2)
        assert not hist.is_full()

        hist.add_user_message("q1")
        hist.add_assistant_message("a1")
        hist.add_user_message("q2")
        hist.add_assistant_message("a2")
        assert hist.is_full()

    def test_messages_have_timestamps(self):
        hist = ConversationHistory(max_turns=10)
        hist.add_user_message("test question")
        hist.add_assistant_message("test answer")

        messages = hist.get_history()
        for msg in messages:
            assert msg.timestamp != ""
            # 应该是 ISO 8601 格式
            assert "T" in msg.timestamp
