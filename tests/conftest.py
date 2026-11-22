import pytest


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("src.fallback.time.sleep", lambda *_: None)


@pytest.fixture
def dlq_file(monkeypatch, tmp_path):
    path = tmp_path / "dlq" / "failed_extractions.jsonl"
    monkeypatch.setattr("src.fallback.DLQ_PATH", path)
    return path
