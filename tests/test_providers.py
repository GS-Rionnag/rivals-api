import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from rivalsdata import PrivacyError, RivalsDataClient, RivalsDataHTTPError
from rivalsdata.extensions import PlayerAnalytics
from rivalsdata.normalize import merge_match, rt_match, tracker_match
from rivalsdata.resources import PlayerMatches, PlayerStats


@pytest.fixture
def captured():
    return json.loads(Path(__file__).with_name("fixtures").joinpath("providers.json").read_text())


@pytest.fixture
def client(monkeypatch):
    with RivalsDataClient() as c:
        c._player_names[1970288503] = "GS-"

        def unexpected(*args, **kwargs):
            raise AssertionError("Unexpected network request")

        monkeypatch.setattr(c, "_post_json", unexpected)
        monkeypatch.setattr(c.providers.rt, "request", unexpected)
        monkeypatch.setattr(c.providers.tracker, "request", unexpected)
        yield c


def test_real_custom_payload_normalizes_all_players_and_hero_kda(captured):
    result = rt_match(captured["rt_custom_match"])
    players = [p for t in result["teams"] for p in t["players"]]
    assert len(players) == 12
    gs = next(p for p in players if str(p["uid"]) == "691218686")
    assert (gs["kills"], gs["deaths"], gs["assists"]) == (28, 5, 7)
    assert [(h["hero_id"], h["kills"], h["deaths"], h["assists"])
            for h in gs["heroes"]] == [(1035, 5, 5, 2), (1011, 23, 0, 5)]
    assert "blocked" not in gs  # Damage taken must not become blocked.


def test_tracker_segments_keep_fields_and_time_units(captured):
    result = tracker_match(captured["tracker_match"])
    player = result["teams"][0]["players"][0]
    assert player["assists"] == 1  # Full detail, not the incorrect summary's 12.
    assert player["play_time"] == player["play_time_ms"] / 1000
    assert "head_kills" in player
    assert "featureHitRate1EnemyHits" in player
    assert "totalDamageTaken" in player["tracker_stats"]
    assert "blocked" not in player
    assert len(player["heroes"]) == 3


def test_merge_preserves_originals_records_conflicts_and_joins_by_identity(captured):
    extra = tracker_match(captured["tracker_match"])
    primary = {"match_uid": extra["match_uid"], "teams": [{"camp": 0, "players": [
        {"uid": 1970288503, "name": "GS-", "assists": 12, "blocked": 90,
         "heroes": [{"hero_id": 1011, "play_time": 20}]},
        {"uid": 9, "name": "Other", "assists": 7}]}]}
    original = deepcopy(primary)
    result = merge_match(primary, extra, "tracker")
    assert primary == original
    player, other = result["teams"][0]["players"]
    assert player["assists"] == 1
    assert player["blocked"] == 90
    assert any(c["field"] == "assists" and c["alternative"] == 12
               for c in player["provider_metadata"]["conflicts"])
    assert "head_kills" in player
    assert other["assists"] == 7 and "tracker_stats" not in other


def test_history_private_primary_falls_back_custom(client, monkeypatch, captured):
    monkeypatch.setattr(client, "_post_json", lambda *a, **k: (_ for _ in ()).throw(PrivacyError("private")))
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: captured["rt_custom_history"])
    result = PlayerMatches(client, 691218686).fetch(mode="custom", season=20)
    assert len(result.matches) == 3
    assert all(m.game_mode_id == 3 and isinstance(m.is_win, bool) for m in result.matches)
    assert result.next_cursor is None
    assert result.provider_metadata.errors[0].source == "rivalsdata"


def test_federated_cursor_deduplicates_across_pages_and_binds_filters(client, monkeypatch):
    def rt_page(path, *, params):
        start = params["skip"]
        ids = range(20) if start == 0 else range(10, 30) if start == 20 else []
        return [{"match_uid": str(i), "match_season": "20", "game_mode_id": 3,
                 "match_time_stamp": i, "match_player": {"k": i}} for i in ids]

    monkeypatch.setattr(client.providers.rt, "request", rt_page)
    monkeypatch.setattr(client, "_post_json", lambda *a: {
        "matches": [{"match_uid": "0", "kills": 900, "season": 20, "game_mode_id": 3}], "next_cursor": None})
    resource = PlayerMatches(client, 123)
    first = resource.fetch(mode="custom", season=20)
    assert len(first.matches) == 20
    assert next(m for m in first.matches if m.match_uid == "0").kills == 900
    second = resource.fetch(mode="custom", season=20, cursor=first.next_cursor)
    assert len(second.matches) == 10
    assert {m.match_uid for m in first.matches}.isdisjoint(m.match_uid for m in second.matches)
    with pytest.raises(ValueError, match="changed filters"):
        resource.fetch(mode="competitive", season=20, cursor=first.next_cursor)
    third = resource.fetch(mode="custom", season=20, cursor=second.next_cursor)
    assert third.matches == [] and third.next_cursor is None


def test_unsupported_teammate_filter_does_not_return_unfiltered_rt(client, monkeypatch):
    monkeypatch.setattr(client, "_post_json", lambda *a: {"matches": [], "next_cursor": None})
    assert PlayerMatches(client, 1).fetch(teammate="2").matches == []


def test_enrichment_failure_does_not_erase_primary_match(client, monkeypatch):
    monkeypatch.setattr(client, "_post_json", lambda *a: {"match_uid": "a", "teams": []})
    failure = lambda *a, **k: (_ for _ in ()).throw(RivalsDataHTTPError("offline"))
    monkeypatch.setattr(client.providers.rt, "request", failure)
    monkeypatch.setattr(client.providers.tracker, "request", failure)
    assert client.matches.get("a").match_uid == "a"
    assert len(client.provider_errors) == 2


def test_hero_enrichment_preserves_counts_and_required_mode(client, monkeypatch, captured):
    primary = [{"hero_id": 1016, "rank": 4,
                "competitive": {"games": 79, "wins": 44, "losses": 35}}]
    monkeypatch.setattr(client, "_post_json", lambda *a: deepcopy(primary))
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: deepcopy(captured["rt_profile"]))
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: deepcopy(captured["tracker_competitive_career"]))
    result = PlayerStats(client, 1970288503).heroes(mode="competitive", season=20)
    loki = next(h for h in result if h.hero_id == 1016)
    assert loki.competitive.games == 79 and loki.rank == 4
    assert loki.competitive.play_time > 0
    assert "tracker_stats" in loki.competitive
    assert "quickplay" not in loki
    assert any(c.field == "games" and c.alternative == 77
               for c in loki.competitive.provider_metadata.conflicts)
    with pytest.raises(ValueError):
        PlayerStats(client, 1970288503).heroes(mode="all")


def test_all_seasons_does_not_merge_tracker_default_into_lifetime(client, monkeypatch, captured):
    monkeypatch.setattr(client, "_post_json", lambda *a: [])
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: captured["rt_profile"])
    # Tracker's request remains the unexpected-network guard.
    PlayerStats(client, 1970288503).heroes(mode="competitive", season="all")


def test_new_endpoint_routing_scope_and_all_season_career(client, monkeypatch):
    calls = []

    def request(path, **kwargs):
        calls.append((path, kwargs))
        if path.endswith("/segments/career"):
            return [{"type": "overview", "stats": {"kills": {"value": 3}}}]
        return {"metadata": {"seasons": [{"id": 18}, {"id": 20}]}}

    monkeypatch.setattr(client.providers.tracker, "request", request)
    analytics = PlayerAnalytics(client, 1970288503)
    result = analytics.career(season="all", mode="competitive")
    assert [row.season for row in result.data] == [18, 20]
    assert [kw["params"]["season"] for path, kw in calls if path.endswith("/segments/career")] == [18, 20]
    analytics.encounters(season=20, local_offset=240)
    assert calls[-1][1]["params"] == {
        "season": 20, "mode": "all", "filter": "encounters", "localOffset": 240}


def test_transport_privacy_rate_limit_cache_and_write_guard(client, monkeypatch):
    from rivalsdata.providers import ProviderTransport

    transport = client.providers.rt
    monkeypatch.setattr(transport, "request", ProviderTransport.request.__get__(transport))
    private = SimpleNamespace(status_code=403, text='{"error":"match history is private"}')
    monkeypatch.setattr(transport.session, "get", lambda *a, **k: private)
    with pytest.raises(PrivacyError):
        transport.request("/player/1")
    limited = SimpleNamespace(status_code=429, text='{"error":"slow down"}')
    monkeypatch.setattr(transport.session, "get", lambda *a, **k: limited)
    with pytest.raises(RivalsDataHTTPError, match="rate limited"):
        transport.request("/player/1")
    with pytest.raises(ValueError, match="read-only"):
        transport.request("/update-player/1", payload={})
    calls = []
    monkeypatch.setattr(transport.session, "get", lambda *a, **k: (
        calls.append(1) or SimpleNamespace(status_code=200, text='{"players":[1]}')))
    first = transport.request("/player/2")
    first["players"].append(9)
    assert transport.request("/player/2")["players"] == [1]
    assert len(calls) == 1


def test_legacy_opt_out_keeps_requests_and_shape(client, monkeypatch):
    client.enrich = False
    calls = []
    monkeypatch.setattr(client, "_post_json", lambda p, data: calls.append((p, data)) or {
        "matches": [], "next_cursor": None})
    result = PlayerMatches(client, 1).fetch(cached=False, mode="3")
    assert calls == [("/player/matches", {"uid": 1, "cursor": None, "mode": 3})]
    assert result.to_dict() == {"matches": [], "next_cursor": None}


def test_reference_snapshot_packaged_and_abilities(client):
    result = client.heroes.reference(1011)
    assert result.scope.snapshot_date == "2026-10-01"
    assert result.data[0].ActiveAbilities


def test_uncached_filters_are_checked_even_when_provider_ignores_them(client, monkeypatch):
    calls = []
    monkeypatch.setattr(client, "_post_json", lambda path, data: calls.append(data) or {
        "matches": [
            {"match_uid": "custom", "game_mode_id": 3, "season": 20, "hero_id": 1016},
            {"match_uid": "ranked", "game_mode_id": 2, "season": 20, "hero_id": 1016},
            {"match_uid": "old", "game_mode_id": 3, "season": 19, "hero_id": 1016},
        ], "next_cursor": None})
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: [])
    result = PlayerMatches(client, 1).fetch(mode="custom", hero="Loki", season=20, cached=False)
    assert [m.match_uid for m in result.matches] == ["custom"]
    assert calls[0]["hero"] == 1016 and calls[0]["mode"] == 3


def test_uncached_teammate_filter_requires_same_team(client, monkeypatch):
    from rivalsdata import Match

    monkeypatch.setattr(client, "_post_json", lambda *a: {"matches": [
        {"match_uid": "same"}, {"match_uid": "enemy"}], "next_cursor": None})
    monkeypatch.setattr(client.matches, "get", lambda uid: Match({"teams": [
        {"camp": 0, "players": [{"uid": 1}, {"uid": 2}]},
        {"camp": 1, "players": [{"uid": 3}]}] if uid == "same" else [
        {"camp": 0, "players": [{"uid": 1}]},
        {"camp": 1, "players": [{"uid": 2}]}]}))
    result = PlayerMatches(client, 1).fetch(teammate="2", cached=False)
    assert [m.match_uid for m in result.matches] == ["same"]


def test_mcp_exposes_additions_and_keeps_existing_history_arguments():
    import asyncio

    pytest.importorskip("mcp")
    pytest.importorskip("mcp_ui_server")
    from rivalsdata.mcp_server import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    assert len(tools) == 43
    assert {"get_match", "get_player_stats", "get_player_encounters",
            "get_player_rank_history", "get_player_crosshairs", "get_community_crosshairs"} <= tools.keys()
    properties = tools["get_player_matches"].inputSchema["properties"]
    assert {"uid_or_name", "cursor", "season", "mode", "hero", "teammate", "cached"} <= properties.keys()
    assert properties["cached"]["default"] is True
