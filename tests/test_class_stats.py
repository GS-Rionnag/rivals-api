import pytest

from rivalsdata import (
    ClassModeStats,
    ClassStatsRecord,
    HeroModeStats,
    hero_class,
    hero_name,
)
from rivalsdata.resources import PlayerStats


class HeroClient:
    def _post_json(self, path, payload):
        self.request = path, payload
        return [
            {"hero_id": 1011, "competitive": {"wins": 9, "losses": 1, "games": 10}},
            {"hero_id": 1018, "competitive": {"wins": 1, "losses": 1, "games": 2}},
            {"hero_id": 10571, "quickplay": {"wins": 3, "losses": 1}},
            {"hero_id": 10572, "competitive": {"wins": 2, "losses": 0}},
            {"hero_id": 10573, "competitive": {"wins": 0, "losses": 2}},
            {"hero_id": 1016, "competitive": {"wins": 3}},
            {"hero_id": 1057, "competitive": {"wins": 4, "losses": 0}},
            {"hero_id": 9999, "competitive": {"wins": 8, "losses": 0}},
        ]


def test_weighted_class_totals_modes_and_exclusions():
    client = HeroClient()
    result = PlayerStats(client, 123).classes(season=20)
    groups = {row.player_class: row for row in result.classes}

    assert client.request == ("/player/stats/heroes", {"uid": 123, "season": 20})
    assert isinstance(groups["tank"], ClassStatsRecord)
    assert isinstance(groups["tank"].competitive, HeroModeStats)
    assert groups["tank"].competitive.win_rate == 83  # 10/12; mean of hero rates is 70
    assert groups["tank"].competitive.games == 12
    assert groups["tank"].quickplay.games == 4
    assert groups["tank"].quickplay.win_rate == 75
    assert groups["support"].competitive.win_rate == 0
    assert groups["dps"].competitive.win_rate == 100
    assert groups["dps"].quickplay.win_rate is None
    assert len(result.excluded) == 3
    assert result.to_dict()["classes"][0]["competitive"]["win_rate"] == 83


def test_roles_use_observed_ids_and_do_not_guess_generic_deadpool():
    assert hero_class(10571) == "tank"
    assert hero_class(10572) == "dps"
    assert hero_class(10573) == "support"
    assert hero_class(1057) is None
    assert hero_name(1055) == "Daredevil"
    assert hero_name(1056) == "Angela"


def test_one_percent_is_not_treated_as_a_fraction():
    row = ClassModeStats({"wins": 1, "losses": 99, "win_rate": 1})
    assert row.win_rate == 1
    assert row.winrate == 1


class SeasonClient:
    def _post_json(self, path, payload):
        self.request = path, payload
        wins = {None: 2, 20: 3, -1: 12}[payload.get("season")]
        return [{"hero_id": 1016, "competitive": {"wins": wins, "losses": 1}}]


@pytest.mark.parametrize("season,payload,wins", [
    (None, {"uid": 123}, 2),
    (20, {"uid": 123, "season": 20}, 3),
    ("all", {"uid": 123, "season": -1}, 12),
    (-1, {"uid": 123, "season": -1}, 12),
])
def test_class_season_selector_uses_the_selected_hero_data(season, payload, wins):
    client = SeasonClient()
    result = PlayerStats(client, 123).classes(season=season)
    assert client.request == ("/player/stats/heroes", payload)
    assert result.classes[1].competitive.wins == wins


def test_detailed_hero_stats_accept_the_same_all_seasons_selector():
    client = SeasonClient()
    rows = PlayerStats(client, 123).heroes(season="all")
    assert client.request == ("/player/stats/heroes", {"uid": 123, "season": -1})
    assert rows[0].competitive.wins == 12


def test_mcp_stats_exposes_all_seasons_and_forwards_the_selector(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    server = pytest.importorskip("rivalsdata.mcp_server", exc_type=ImportError)
    client = SeasonClient()
    client.get_player = lambda value: SimpleNamespace(stats=PlayerStats(client, 123))
    monkeypatch.setattr(server, "_call", lambda fn, *a, **kw: fn(client, *a, **kw))
    result = server.get_player_stats("123", category="classes", season="all")
    assert client.request == ("/player/stats/heroes", {"uid": 123, "season": -1})
    assert result.classes[1].competitive.wins == 12
    tools = asyncio.run(server.mcp.list_tools())
    schema = next(tool.inputSchema for tool in tools if tool.name == "get_player_stats")
    assert {"const": "all", "type": "string"} in schema["properties"]["season"]["anyOf"]
