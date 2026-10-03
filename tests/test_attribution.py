from copy import deepcopy
from types import SimpleNamespace

import pytest

from rivals_api import Match, MatchHistory, RivalsClient, RivalsDataHTTPError
from rivals_api.attribution import attribute_match
from rivals_api.resources import PlayerHeroes, PlayerMatches, PlayerStats


def detail(heroes, *, outcome=True, uid=691218686):
    return {"match_uid": "match", "teams": [{"players": [{
        "uid": uid, "is_win": outcome,
        "heroes": [{"hero_id": hero, "play_time": duration} for hero, duration in heroes]}]}],
        "provider_metadata": {"sources": ["rivalsdata"], "evidence": {
            "rivalsdata": {"complete": True}}}}


@pytest.mark.parametrize("heroes,reason", [
    ([(1055, 10), (1056, 10)], "tied_hero_playtime"),
    ([(1055, 10), (1056, None)], "missing_or_invalid_hero_playtime"),
    ([(1055, float('nan'))], "missing_or_invalid_hero_playtime"),
    ([(1055, -1)], "missing_or_invalid_hero_playtime"),
    ([(1055, True)], "missing_or_invalid_hero_playtime"),
    ([(1055, 0)], "missing_or_invalid_hero_playtime"),
    ([(1055, 5), (1055, 6)], "duplicate_hero_records"),
])
def test_no_summary_fallback_or_arbitrary_tie_break(heroes, reason):
    assignment, error = attribute_match(detail(heroes), 691218686, "GS-4", {
        "hero_id": 1055, "is_win": True})
    assert assignment is None and error == reason


def test_completed_outcome_and_longest_hero_override_summary():
    assignment, error = attribute_match(detail([(1055, 20), (1056, 80)], outcome=False),
                                        691218686, "GS-4", {"hero_id": 1055, "is_win": True})
    assert error is None
    assert assignment["hero_id"] == 1056 and assignment["is_win"] is False


def test_raw_source_records_are_compared_without_blending_times():
    rd = detail([(1055, 90), (1056, 10)])
    rt = {"match_uid": "match", "match_players": [{"player_uid": 691218686,
        "is_win": True, "player_heroes": [{"hero_id": 1055, "play_time": 5},
                                          {"hero_id": 1056, "play_time": 95}]}]}
    rd["provider_metadata"]["responses"] = {"rivalsdata": deepcopy(rd), "rivalstracker": rt}
    assert attribute_match(rd, 691218686, "GS-4", {}) == (None, "conflicting_longest_hero")
    rt["match_players"][0]["player_heroes"][0]["play_time"] = 100
    assignment, error = attribute_match(rd, 691218686, "GS-4", {})
    assert error is None and assignment["hero_id"] == 1055
    rt["match_players"][0]["is_win"] = False
    assert attribute_match(rd, 691218686, "GS-4", {}) == (None, "conflicting_match_outcome")


def test_duplicate_identity_is_unresolved():
    data = detail([(1055, 50)])
    data["teams"][0]["players"] *= 2
    assert attribute_match(data, 691218686, "GS-4", {})[0] is None


@pytest.fixture
def client(monkeypatch):
    with RivalsClient() as client:
        client._player_names[691218686] = "GS-4"
        calls = []
        rows = [{"match_uid": "win", "hero_id": 1056, "is_win": True, "game_mode_id": 2},
                {"match_uid": "loss", "hero_id": 1055, "is_win": False, "game_mode_id": 2},
                {"match_uid": "win", "hero_id": 1056, "is_win": True, "game_mode_id": 2}]

        def history(self, **filters):
            calls.append(filters)
            return MatchHistory({"matches": rows, "provider_metadata": {
                "sources": ["rivalsdata"], "errors": []}})

        monkeypatch.setattr(PlayerMatches, "fetch", history)
        monkeypatch.setattr(client.matches, "get", lambda identifier: Match(detail(
            [(1055, 80), (1056, 20)] if identifier == "win" else [(1055, 20), (1056, 80)],
            outcome=identifier == "win")))
        monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: {
            "metadata": {"currentSeason": 20}})
        client.calls = calls
        yield client


def test_simple_hero_class_api_deduplicates_and_reuses_calculation(client):
    stats = PlayerStats(client, 691218686)
    heroes = stats.heroes()
    assert {r.hero_name: (r.games, r.wins, r.losses, r.win_rate) for r in heroes} == {
        "Daredevil": (1, 1, 0, 100), "Angela": (1, 0, 1, 0)}
    classes = stats.classes()
    assert {r.player_class: (r.games, r.wins) for r in classes.classes} == {
        "dps": (1, 1), "tank": (1, 0)}
    assert classes.metadata.coverage.matches_found == 2
    assert classes.metadata.coverage.matches_unresolved == 0
    assert len(client.calls) == 1
    assert client.calls[0]["season"] == 20
    assert PlayerHeroes(client, 691218686).fetch()[0].hero_name == "Daredevil"
    stats.heroes(season="all", mode="quickplay")
    assert client.calls[-1]["season"] is None and client.calls[-1]["mode"] == "quickplay"


def test_unresolved_coverage_is_available_even_with_empty_hero_list(client, monkeypatch):
    monkeypatch.setattr(client.matches, "get", lambda *a: Match(detail([(1055, 20), (1056, 20)])))
    result = PlayerStats(client, 691218686).hero_win_rates(season=20)
    assert result.data == []
    assert result.metadata.coverage.matches_found == 2
    assert result.metadata.coverage.matches_unresolved == 2
    assert not result.metadata.coverage.complete_game_history_verified
    assert client._attribution_cache == {}


def test_detail_outage_does_not_become_summary_attribution(client, monkeypatch):
    def failure(*a):
        raise RivalsDataHTTPError("offline")
    monkeypatch.setattr(client.matches, "get", failure)
    result = PlayerStats(client, 691218686).hero_win_rates(season=20)
    assert result.data == [] and len(result.metadata.provider_errors) == 2


def test_hero_class_season_scope_and_current_fallback(client, monkeypatch):
    def tracker(*a, **k):
        raise RivalsDataHTTPError("Tracker unavailable")

    monkeypatch.setattr(client.providers.tracker, "request", tracker)
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: {"season": "20"})
    stats = PlayerStats(client, 691218686)
    for season, expected in [("current", 20), (19, 19), ("all", "all")]:
        heroes = stats.hero_win_rates(season=season)
        classes = stats.class_win_rates(season=season)
        assert heroes.metadata.scope.season == classes.metadata.scope.season == expected
        assert classes.metadata.coverage.matches_attributed == heroes.metadata.coverage.matches_attributed
        assert client.calls[-1]["season"] == (None if expected == "all" else expected)


def test_mcp_defaults_and_schemas_have_no_character_method(client, monkeypatch):
    import asyncio
    server = pytest.importorskip("rivalsdata.mcp_server", exc_type=ImportError)
    monkeypatch.setattr(client, "get_player", lambda *a: SimpleNamespace(stats=PlayerStats(client, 691218686)))
    monkeypatch.setattr(server, "_call", lambda fn, *a, **kw: fn(client, *a, **kw))
    assert len(server.get_player_heroes("GS-4").data) == 2
    assert server.get_player_stats("GS-4").metadata.scope.season == 20
    assert server.get_player_stats("GS-4", category="classes", season="all").metadata.scope.season == "all"
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name in ("get_player_heroes", "get_player_hero_win_rates", "get_player_class_win_rates"):
        assert "method" not in tools[name].inputSchema["properties"]
    assert tools["get_player_stats"].inputSchema["properties"]["mode"]["default"] == "all"


def test_one_percent_canonical_rate_does_not_become_one_hundred_percent():
    from rivals_api.models import HeroStatsRecord
    row = HeroStatsRecord({"hero_id": 1055, "games": 100, "wins": 1,
                           "losses": 99, "win_rate": 1, "win_rate_pct": 1.0})
    assert row.win_rate == 1


def test_tracker_summary_fills_empty_successful_rd_section(client, monkeypatch):
    monkeypatch.setattr(client, "_post_json", lambda *a, **k: [{"hero_id": 1055, "competitive": None}])
    monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: {})
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: [{
        "type": "hero", "attributes": {"heroId": 1055, "season": 20, "mode": "competitive"},
        "stats": {"matchesPlayed": {"value": 19}, "matchesWon": {"value": 8}}}])
    rows = PlayerStats(client, 691218686).summary_heroes(mode="competitive", season=20)
    assert rows[0].hero_name == "Daredevil"
    assert rows[0].competitive.games == 19 and rows[0].competitive.wins == 8
    assert rows[0].competitive.provider_metadata.sources == ["tracker"]


def test_tracker_only_completed_detail_uses_unique_verified_name():
    data = detail([(1055, 20)], uid=None)
    player = data["teams"][0]["players"][0]
    player["name"] = "GS-4"
    player["tracker_account_id"] = "tracker-uuid"
    assert attribute_match(data, 691218686, "GS-4", {})[0]["hero_id"] == 1055
    assert attribute_match(data, 691218686, "Other", {})[0] is None
    data["teams"][0]["players"].append(deepcopy(player))
    assert attribute_match(data, 691218686, "GS-4", {})[0] is None


def test_valid_cached_source_details_reused_despite_optional_outage(client, monkeypatch):
    for identifier in ("win", "loss"):
        cached = detail([(1055, 80)], outcome=identifier == "win")
        cached["provider_metadata"]["errors"] = [{"source": "tracker", "error": "offline"}]
        monkeypatch.setitem(client._match_detail_cache, (identifier, True), cached)

    def unexpected(*a):
        raise AssertionError("Verified cached detail should not be fetched again")

    monkeypatch.setattr(client.matches, "get", unexpected)
    stats = PlayerStats(client, 691218686)
    assert stats.hero_win_rates(season=20).data[0].games == 2
    result = stats.class_win_rates(season=20)
    assert result.data[0].games == 2
    assert len(result.metadata.provider_errors) == 2


def test_all_hero_class_modes_combine_only_competitive_and_quickplay(client, monkeypatch):
    rows = [{"match_uid": "win", "is_win": True, "game_mode_id": 2},
            {"match_uid": "loss", "is_win": False, "game_mode_id": 1},
            {"match_uid": "custom", "is_win": True, "game_mode_id": 3},
            {"match_uid": "arcade", "is_win": True, "game_mode_id": 4}]

    def history(self, **filters):
        return MatchHistory({"matches": rows, "provider_metadata": {"sources": [], "errors": []}})

    monkeypatch.setattr(PlayerMatches, "fetch", history)
    monkeypatch.setattr(client.matches, "get", lambda identifier: Match(
        detail([(1055, 80)], outcome=identifier == "win")))
    stats = PlayerStats(client, 691218686)
    hero = stats.heroes()[0]
    assert (hero.games, hero.wins, hero.losses, hero.win_rate_pct) == (2, 1, 1, 50)
    assert hero.all.games == 2 and hero.mode == "all"
    assert stats.classes().classes[0].all.games == 2
    assert stats.heroes(mode="competitive")[0].games == 1
    assert stats.heroes(mode="quickplay")[0].wins == 0


@pytest.mark.parametrize("mode", [None, "custom", "quick-match", 1])
def test_invalid_canonical_modes_are_rejected(client, mode):
    with pytest.raises(ValueError, match="competitive, quickplay, or all"):
        PlayerStats(client, 691218686).heroes(mode=mode)
