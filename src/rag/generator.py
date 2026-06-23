"""DeepSeek LLM 调用封装"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Generator:
    """封装 DeepSeek Chat API 调用。

    支持同步（generate）和异步（agenerate）两种方式。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def _create_chat(self):
        """创建 ChatDeepSeek 实例（每次调用新建以支持不同参数）"""
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=self._model,
            api_key=self._api_key,
            api_base=self._base_url,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    def generate(self, messages: list[dict]) -> str:
        """同步生成回答。

        Args:
            messages: LLM 消息列表 [{"role": ..., "content": ...}, ...]

        Returns:
            LLM 生成的文本回答
        """
        chat = self._create_chat()
        response = chat.invoke(messages)
        return response.content

    async def agenerate(self, messages: list[dict]) -> str:
        """异步生成回答"""
        chat = self._create_chat()
        response = await chat.ainvoke(messages)
        return response.content
