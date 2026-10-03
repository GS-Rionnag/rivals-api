import json
from pathlib import Path

import pytest

from rivals_api import RivalsClient, RivalsDataHTTPError
from rivals_api.resources import PlayerMatches


@pytest.fixture
def history():
    return json.loads(Path(__file__).with_name("fixtures").joinpath(
        "gs4_tracker_history.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    with RivalsClient() as client:
        client._player_names[691218686] = "GS-4"
        monkeypatch.setattr(client, "_post_json", lambda *a, **k: {
            "matches": [], "next_cursor": None})
        monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: [])
        yield client


def test_gs4_competitive_history_survives_empty_other_sources(client, monkeypatch, history):
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: history)
    page = PlayerMatches(client, 691218686).fetch(limit=20, mode="competitive")
    assert [m.match_uid for m in page.matches] == [
        "5521403_1790383734_1231008_11001_11",
        "5518016_1790383327_1434006_11001_11"]
    assert all(m.game_mode_id == 2 for m in page.matches)
    assert page.matches[0].get_details  # History models retain the client.
    assert page.provider_metadata.sources == ["rivalsdata", "rivalstracker", "tracker"]
    assert page.next_cursor is None


def test_tracker_cursor_overflow_deduplication_and_identity(client, monkeypatch, history):
    calls = []

    def request(path, *, params):
        calls.append((path, params))
        if params["next"] is None:
            return {**history, "metadata": {"next": "opaque-token"}}
        return {"matches": [history["matches"][1]], "metadata": {"next": None}}

    monkeypatch.setattr(client.providers.tracker, "request", request)
    resource = PlayerMatches(client, 691218686)
    first = resource.fetch(limit=1, mode="competitive")
    second = resource.fetch(limit=1, mode="competitive", cursor=first.next_cursor)
    assert first.matches[0].match_uid != second.matches[0].match_uid
    assert second.next_cursor is None
    assert calls[-1][1]["next"] == "opaque-token"
    assert calls[0][0].endswith("/GS-4")
    history["matches"][1]["segments"][0]["metadata"]["platformInfo"]["platformUserIdentifier"] = "Other"
    history["matches"][2]["segments"].append(history["matches"][2]["segments"][0])
    assert resource.fetch(limit=20, mode="competitive").matches == []


def test_tracker_unverified_season_is_explicit(client, monkeypatch, history):
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: history)
    page = PlayerMatches(client, 691218686).fetch(limit=20, season=19, mode="competitive")
    assert page.matches == []
    assert "unverified season" in page.provider_metadata.errors[0].error


def test_tracker_failure_preserves_successful_history(client, monkeypatch):
    monkeypatch.setattr(client, "_post_json", lambda *a, **k: {
        "matches": [{"match_uid": "rd", "game_mode_id": 2}], "next_cursor": None})

    def failure(*args, **kwargs):
        raise RivalsDataHTTPError("blocked")

    monkeypatch.setattr(client.providers.tracker, "request", failure)
    page = PlayerMatches(client, 691218686).fetch(limit=1, mode="competitive")
    assert page.matches[0].match_uid == "rd"
    assert page.provider_metadata.errors[0].source == "tracker"
