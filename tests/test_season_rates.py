from types import SimpleNamespace

import pytest

from rivals_api import Match, MatchHistory, RivalsClient, RivalsDataHTTPError
from rivals_api.resources import PlayerMatches, PlayerStats
from rivals_api.season_rates import counts


def matches(mode_id, games, wins):
    return [{"match_uid": f"{mode_id}-{i}", "game_mode_id": mode_id,
             "is_win": i < wins, "season": 20} for i in range(games)]


@pytest.fixture
def setup(monkeypatch):
    with RivalsClient() as client:
        client._player_names[691218686] = "GS-4"
        data = {"rd_games": 26, "rt": {"competitive": (25, 11), "quickplay": (35, 17)},
                "tracker": {"competitive": (25, 11), "quickplay": (35, 17)},
                "rows": matches(2, 25, 11) + matches(1, 35, 17), "calls": []}
        monkeypatch.setattr(client, "_post_json", lambda *a, **k: {
            "uid": 691218686, "rank_game_season": {"1001020": {
                "rank_game_id": 20, "battle_count": data["rd_games"], "win_count": 11}}})

        def rt(path, *, params):
            data["calls"].append(("rt", params))
            stats = {}
            for mode, pair in data["rt"].items():
                prefix = "ranked" if mode == "competitive" else "unranked"
                stats.update({prefix + "_matches": pair[0], prefix + "_matches_wins": pair[1]})
            return {"player": {"_id": 691218686}, "stats": stats}

        def tracker(path, *, params=None):
            data["calls"].append(("tracker", params))
            if not path.endswith("/segments/career"):
                return {"metadata": {"currentSeason": 20}}
            mode = "quickplay" if params["mode"] == "quick-match" else params["mode"]
            pair = data["tracker"].get(mode)
            if pair is None:
                return []
            return [{"type": "overview", "attributes": {
                "season": data.get("tracker_season", params["season"]), "mode": params["mode"]},
                "stats": {"matchesPlayed": {"value": pair[0]}, "matchesWon": {"value": pair[1]}}}]

        def history(self, **filters):
            data["calls"].append(("history", filters))
            if data.get("history_error"):
                raise RivalsDataHTTPError("history offline")
            return MatchHistory({"matches": data["rows"], "provider_metadata": {
                "sources": ["rivalstracker", "tracker"], "errors": []}})

        def unexpected(*a, **k):
            raise AssertionError("Unexpected detail lookup")

        monkeypatch.setattr(client.providers.rt, "request", rt)
        monkeypatch.setattr(client.providers.tracker, "request", tracker)
        monkeypatch.setattr(client.matches, "get", unexpected)
        monkeypatch.setattr(PlayerMatches, "fetch", history)
        yield client, data


def test_all_default_uses_disjoint_mode_counts_and_excludes_custom(setup):
    client, data = setup
    data["rows"] += matches(3, 5, 5) + matches(4, 7, 7)
    stats = PlayerStats(client, 691218686)
    result = stats.win_rate()
    assert (result.games, result.wins, result.losses, result.win_rate_pct) == (60, 28, 32, 46.67)
    assert result.metadata.scope.mode == "all" and result.metadata.scope.season == 20
    assert result.metadata.coverage.history_matches_record
    assert result.metadata.by_mode.competitive.selection_reason == "provider_record_agreement"
    assert result.metadata.provider_records[0].eligible is False
    assert result.metadata.provider_records[0].games == 26
    assert stats.win_rate(mode="competitive").win_rate_pct == 44
    assert stats.win_rate(mode="quickplay").win_rate_pct == 48.57
    assert {params["mode"] for source, params in data["calls"]
            if source == "tracker" and params} == {"competitive", "quick-match"}


def test_history_match_can_outweigh_larger_disagreeing_record(setup):
    client, data = setup
    data["rt"]["competitive"] = (10, 5)
    data["tracker"]["competitive"] = (8, 4)
    data["rows"] = matches(2, 8, 4)
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.games == 8 and result.metadata.by_mode.competitive.source == "tracker"
    assert result.metadata.by_mode.competitive.selection_reason == "matches_tracked_history"
    assert len(result.metadata.by_mode.competitive.conflicts) == 1


def test_no_averaging_when_disagreement_remains_unresolved(setup):
    client, data = setup
    data["rt"]["competitive"] = (10, 6)
    data["tracker"]["competitive"] = (11, 6)
    data["rows"] = matches(2, 2, 1)
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.win_rate_pct == 60
    assert result.metadata.selection_uncertain
    assert result.metadata.by_mode.competitive.conflicts[0].games == 11


def test_wrong_season_overview_falls_back_to_history(setup):
    client, data = setup
    data["rt"] = {}
    data["tracker_season"] = 19
    data["rows"] = matches(2, 3, 2)
    result = PlayerStats(client, 691218686).win_rate(mode="competitive", season=20)
    assert (result.games, result.wins, result.win_rate_pct) == (3, 2, 66.67)
    assert result.metadata.coverage.uses_history_fallback
    assert result.metadata.by_mode.competitive.source == "tracked_history"
    assert result.metadata.provider_errors


def test_career_record_survives_history_outage(setup):
    client, data = setup
    data["history_error"] = True
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.win_rate_pct == 44
    assert not result.metadata.coverage.history_matches_record
    assert result.metadata.provider_errors[0].source == "history"


def test_conflicting_counts_are_rejected_when_below_verified_history(setup):
    client, data = setup
    data["rt"]["competitive"] = (20, 11)
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.metadata.by_mode.competitive.source == "tracker"
    assert result.metadata.by_mode.competitive.rejected_records[0].reason == "contradicts_tracked_history"


def test_overall_outcomes_do_not_require_hero_playtime(setup, monkeypatch):
    client, data = setup
    data["rt"] = {}
    data["tracker"] = {}
    data["rows"] = [{"match_uid": "unknown-hero", "game_mode_id": 2, "is_win": None}]
    monkeypatch.setattr(client.matches, "get", lambda *a: Match({
        "teams": [{"players": [{"uid": 691218686, "is_win": True, "heroes": []}]}],
        "provider_metadata": {"sources": ["rivalsdata"], "evidence": {"rivalsdata": {"complete": True}}}}))
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert (result.games, result.wins, result.win_rate_pct) == (1, 1, 100)


def test_unknown_results_do_not_become_losses_in_history_fallback(setup, monkeypatch):
    client, data = setup
    data["rt"] = {}
    data["tracker"] = {}
    data["rows"] = matches(2, 2, 1)
    data["rows"][1]["is_win"] = None
    def failed(*a):
        raise RivalsDataHTTPError("offline")
    monkeypatch.setattr(client.matches, "get", failed)
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.games == 1 and result.losses == 0
    assert result.metadata.coverage.unknown_results == 1


def test_mode_scoped_cache_and_compatibility_alias(setup):
    client, data = setup
    resource = PlayerMatches(client, 691218686)
    assert resource.fetch_win_rate(season=20).games == 60
    previous = len(data["calls"])
    assert PlayerStats(client, 691218686).win_rate(season=20).games == 60
    assert len(data["calls"]) == previous
    assert resource.fetch_win_rate(season=20, mode="competitive").games == 25
    assert resource.fetch_win_rate(season=20, method="exact").matches == 60
    assert resource.fetch_win_rate(season=20, method="estimate").games == 60


def test_overall_mcp_schema_and_default_scope(setup, monkeypatch):
    import asyncio
    client, _data = setup
    server = pytest.importorskip("rivals_api.mcp_server", exc_type=ImportError)
    monkeypatch.setattr(client, "get_player", lambda *a: SimpleNamespace(stats=PlayerStats(client, 691218686)))
    monkeypatch.setattr(server, "_call", lambda fn, *a, **kw: fn(client, *a, **kw))
    assert server.get_player_win_rate("GS-4").games == 60
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    schema = tools["get_player_win_rate"].inputSchema["properties"]
    assert "method" not in schema and "cached" not in schema
    assert schema["mode"]["default"] == "all"
    assert set(schema["mode"]["enum"]) == {"all", "competitive", "quickplay"}


@pytest.mark.parametrize("games,wins", [(True, 1), (1, True), (2, 3), (float('nan'), 0), (-1, 0), (1.5, 1)])
def test_invalid_career_counts_are_not_selected(games, wins):
    assert counts(games, wins) is None


def test_zero_season_record_has_no_percentage(setup):
    client, data = setup
    data["rt"]["competitive"] = (0, 0)
    data["tracker"]["competitive"] = (0, 0)
    data["rows"] = []
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert result.games == 0 and result.win_rate_pct is None
    assert not result.metadata.coverage.history_matches_record


def test_conflicting_summary_outcome_uses_completed_detail_without_hero_attribution(setup, monkeypatch):
    client, data = setup
    data["rt"] = {}
    data["tracker"] = {}
    data["rows"] = [{"match_uid": "disputed", "game_mode_id": 2, "is_win": True,
                     "provider_metadata": {"conflicts": [{"field": "is_win"}]}}]
    monkeypatch.setattr(client.matches, "get", lambda *a: Match({
        "teams": [{"players": [{"uid": 691218686, "is_win": False, "heroes": []}]}],
        "provider_metadata": {"sources": ["rivalsdata"], "evidence": {"rivalsdata": {"complete": True}}}}))
    result = PlayerStats(client, 691218686).win_rate(mode="competitive")
    assert (result.wins, result.losses, result.win_rate_pct) == (0, 1, 0)


def test_all_seasons_uses_tracked_history_without_career_default_contamination(setup):
    client, data = setup
    result = PlayerStats(client, 691218686).win_rate(season="all")
    assert result.games == 60 and result.metadata.scope.season == "all"
    assert result.metadata.coverage.uses_history_fallback
    assert not any(source in ("rt", "tracker") for source, _params in data["calls"])


@pytest.mark.parametrize("mode", [None, "arcade", "custom", "quick-match"])
def test_invalid_overall_mode_fails_before_provider_requests(setup, mode):
    client, data = setup
    with pytest.raises(ValueError, match="competitive, quickplay, or all"):
        PlayerStats(client, 691218686).win_rate(mode=mode)
    assert data["calls"] == []
