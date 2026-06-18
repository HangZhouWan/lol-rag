# tests/test_repository.py
import json
import os
import tempfile
import pytest
from src.repository import FetchRepository
from src.config import MAX_RETRIES


class TestFetchRepository:
    @pytest.fixture
    def repo(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, ".fetch_record.json")
        repo = FetchRepository(record_path=path)
        yield repo
        # cleanup
        if os.path.exists(path):
            os.remove(path)
        os.rmdir(tmp)

    def test_should_fetch_new_url(self, repo):
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_fetch_force(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/tmp/安妮.md")
        assert repo.should_fetch("http://test.com/yx1.html", force=True) is True

    def test_should_skip_success_with_existing_file(self, repo):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            repo.record_success("http://test.com/yx1.html", "heroes", "安妮", path)
            assert repo.should_fetch("http://test.com/yx1.html") is False
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_should_refetch_if_file_missing(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/nonexistent/安妮.md")
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_retry_failed_under_limit(self, repo):
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        # retries = 2, MAX_RETRIES = 3 → 2 < 3 → should retry
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_skip_failed_at_limit(self, repo):
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        # retries = 3, MAX_RETRIES = 3 → 3 < 3 is False → should not retry
        assert repo.should_fetch("http://test.com/yx1.html") is False

    def test_get_pending_urls(self, repo):
        urls = ["http://test.com/yx1.html", "http://test.com/yx2.html"]
        repo.record_success("http://test.com/yx2.html", "heroes", "盖伦", "/tmp/盖伦.md")
        # yx2 is marked success but file doesn't exist, so it stays pending
        # yx1 is new, so it's pending too
        pending = repo.get_pending_urls(urls)
        assert pending == ["http://test.com/yx1.html", "http://test.com/yx2.html"]
        assert len(pending) == 2

    def test_save_and_reload(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/tmp/安妮.md")
        repo.save()

        repo2 = FetchRepository(record_path=repo.record_path)
        repo2.load()
        assert "http://test.com/yx1.html" in repo2.records
        assert repo2.records["http://test.com/yx1.html"].status == "success"
        assert repo2.records["http://test.com/yx1.html"].name == "安妮"

    def test_record_failure_new_url(self, repo):
        repo.record_failure("http://test.com/yx_new.html", "heroes", "ConnectionError")
        rec = repo.records["http://test.com/yx_new.html"]
        assert rec.status == "failed"
        assert rec.retries == 1
        assert rec.error == "ConnectionError"
        assert rec.last_attempt is not None

    def test_load_missing_file(self, repo):
        # By default repo fixture uses a non-existent file path; load() should handle it gracefully.
        new_repo = FetchRepository(record_path="/nonexistent/path/.fetch_record.json")
        new_repo.load()
        assert new_repo.records == {}
