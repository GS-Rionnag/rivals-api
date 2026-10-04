import pytest


@pytest.fixture(autouse=True)
def isolate_match_cache(tmp_path, monkeypatch):
    from rivals_api.client import _MATCH_DETAIL_CACHE, _MATCH_HISTORY_CACHE
    from rivals_api.rate_limits import _GATES

    _GATES.clear()
    monkeypatch.setattr("rivals_api.rate_limits.time.sleep", lambda seconds: None)
    monkeypatch.setenv("RIVALS_API_CACHE_DIR", str(tmp_path / "cache"))
    _MATCH_DETAIL_CACHE.clear()
    _MATCH_HISTORY_CACHE.clear()
    _GATES.clear()
    yield
    _MATCH_DETAIL_CACHE.clear()
    _MATCH_HISTORY_CACHE.clear()
