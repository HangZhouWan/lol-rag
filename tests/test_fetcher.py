# tests/test_fetcher.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.fetcher import Fetcher
from src.config import MAX_RETRIES, RETRY_BACKOFF


class TestFetcher:
    @pytest.mark.asyncio
    async def test_fetch_one_success(self):
        fetcher = Fetcher(delay=0)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="<html>hero page</html>")

        mock_session = MagicMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert url == "http://test.com/yx1.html"
        assert html == "<html>hero page</html>"
        assert error is None

    @pytest.mark.asyncio
    async def test_fetch_one_retry_then_success(self):
        fetcher = Fetcher(delay=0, max_retries=3, backoff=[0, 0, 0])
        fail_resp = MagicMock()
        fail_resp.status = 500
        ok_resp = MagicMock()
        ok_resp.status = 200
        ok_resp.text = AsyncMock(return_value="<html>ok</html>")

        mock_session = MagicMock()
        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            resp = ok_resp if call_count[0] == 3 else fail_resp

            class _CtxMgr:
                async def __aenter__(self): return resp
                async def __aexit__(self, *a): pass
            return _CtxMgr()

        mock_session.get = mock_get

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert html == "<html>ok</html>"
        assert error is None
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_fetch_one_all_retries_fail(self):
        fetcher = Fetcher(delay=0, max_retries=2, backoff=[0, 0])
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection error")

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert html is None
        assert "Connection error" in error

    @pytest.mark.asyncio
    async def test_fetch_all_concurrency(self):
        fetcher = Fetcher(delay=0, concurrency=3)

        urls = [f"http://test.com/yx{i}.html" for i in range(10)]

        async def fetch_one(session, url):
            return (url, f"html_{url}", None)

        fetcher.fetch_one = fetch_one
        results = await fetcher.fetch_all(urls)
        assert len(results) == 10
        assert all(r[1] is not None for r in results)
