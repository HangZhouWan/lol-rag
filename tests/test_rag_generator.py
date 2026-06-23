# tests/test_rag_generator.py
from unittest.mock import MagicMock, patch

import pytest

from src.rag.generator import Generator


@pytest.fixture
def generator():
    return Generator(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        max_tokens=1024,
        temperature=0.3,
    )


class TestGeneratorInit:
    def test_creates_client_with_correct_params(self):
        gen = Generator(
            api_key="sk-abc",
            base_url="https://custom.api.com",
            model="custom-model",
            max_tokens=512,
            temperature=0.7,
        )
        assert gen._api_key == "sk-abc"
        assert gen._base_url == "https://custom.api.com"
        assert gen._model == "custom-model"
        assert gen._max_tokens == 512
        assert gen._temperature == 0.7


class TestGeneratorGenerate:
    def test_generate_returns_string(self, generator):
        with patch("langchain_deepseek.ChatDeepSeek") as mock_chat:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "这是测试回答 [1]"
            mock_instance.invoke.return_value = mock_response
            mock_chat.return_value = mock_instance

            result = generator.generate([{"role": "user", "content": "测试"}])
            assert isinstance(result, str)
            assert result == "这是测试回答 [1]"

    def test_generate_calls_llm_with_correct_params(self, generator):
        with patch("langchain_deepseek.ChatDeepSeek") as mock_chat:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "回答"
            mock_instance.invoke.return_value = mock_response
            mock_chat.return_value = mock_instance

            messages = [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "q"},
            ]
            generator.generate(messages)

            mock_chat.assert_called_once_with(
                model="deepseek-chat",
                api_key="sk-test",
                api_base="https://api.deepseek.com",
                max_tokens=1024,
                temperature=0.3,
            )
            mock_instance.invoke.assert_called_once_with(messages)


class TestGeneratorAgenerate:
    @pytest.mark.asyncio
    async def test_agenerate_returns_string(self, generator):
        with patch("langchain_deepseek.ChatDeepSeek") as mock_chat:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "异步回答"

            async def _mock_ainvoke(*args, **kwargs):
                return mock_response
            mock_instance.ainvoke = _mock_ainvoke
            mock_chat.return_value = mock_instance

            result = await generator.agenerate([{"role": "user", "content": "async"}])
            assert result == "异步回答"
