"""对话历史管理 — 内存 deque，自动截断"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

from src.rag.models import Message

logger = logging.getLogger(__name__)


class ConversationHistory:
    """维护内存中的对话历史，自动截断超出上限的轮次。

    使用 deque 存储 Message 对象。
    每轮 = 1 条 user + 1 条 assistant 消息。
    max_turns 控制最大轮数，超出时自动丢弃最早的消息。
    """

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._messages: deque[Message] = deque()

    def _now_iso(self) -> str:
        """返回当前 UTC 时间的 ISO 8601 字符串"""
        return datetime.now(timezone.utc).isoformat()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        msg = Message(role="user", content=content, timestamp=self._now_iso())
        self._messages.append(msg)
        self._maybe_truncate()

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        msg = Message(role="assistant", content=content, timestamp=self._now_iso())
        self._messages.append(msg)
        self._maybe_truncate()

    def get_history(self) -> list[Message]:
        """返回完整历史（副本）"""
        return list(self._messages)

    def clear(self) -> None:
        """清空对话历史"""
        self._messages.clear()
        logger.debug("对话历史已清空")

    def turn_count(self) -> int:
        """返回已完成的轮数（user+assistant 配对）"""
        return len(self._messages) // 2

    def is_full(self) -> bool:
        """历史是否已达到上限"""
        return self.turn_count() >= self._max_turns

    def _maybe_truncate(self) -> None:
        """如果超过上限，自动截断最早的轮次"""
        max_messages = self._max_turns * 2
        while len(self._messages) > max_messages:
            # 丢弃最早的两条消息（一轮）
            removed_user = self._messages.popleft()
            if self._messages and self._messages[0].role == "assistant":
                removed_assistant = self._messages.popleft()
                logger.debug("对话历史截断: 丢弃轮次 %s / %s",
                             removed_user.content[:30],
                             removed_assistant.content[:30])
