import json

import pytest

from rivals_api import (
    Character,
    GameMode,
    GameplayMode,
    Map,
    Match,
    MatchHistory,
    Platform,
    Rank,
    Season,
)
from rivals_api.models import MatchPlayer, MatchTeam, RankRecord
from rivals_api.normalize import rt_history, rt_match, tracker_match


def test_history_resolves_names_without_fetching_details():
    row = {"match_uid": "match-1", "map_id": 1288, "game_mode_id": 3,
           "game_play_mode_id": 200, "platform": 1, "hero_id": 1016,
           "rank_level": 15, "season": 20}
    match = MatchHistory({"matches": [row]}).matches[0]

    assert isinstance(match.map, Map)
    assert str(match.map) == "Hell's Heaven"
    assert f"Map: {match.map}" == "Map: Hell's Heaven"
    assert match.map.name == "Hell's Heaven"
    assert match.map.location == "Hydra Charteris Base"
    assert match.map.id == 1288
    assert match.map.gameplay_mode.name == "Domination"
    assert str(match.game_mode) == "Custom"
    assert match.game_mode.id == 3
    assert isinstance(match.gameplay_mode, GameplayMode)
    assert match.gameplay_mode.name == "Domination"
    assert match.gameplay_mode.id == 200
    assert match.gameplay_mode is match.game_play_mode
    assert str(match.platform) == "PC"
    assert match.platform.id == match.platform_id == 1
    assert str(match.hero) == "Loki"
    assert match.hero.id == 1016
    assert str(match.rank) == "Diamond 1"
    assert match.rank.tier == "Diamond"
    assert match.rank.division == 1
    assert str(match.season_info) == "Season 10"
    assert match.season_info.id == 20
    assert match.raw == row
    assert isinstance(row["platform"], int)


def test_gameplay_codes_use_the_map_context_not_a_global_guess():
    convoy = Match(map_id=1245, game_play_mode_id=200)
    domination = Match(map_id=1288, game_play_mode_id=200)
    assert str(convoy.gameplay_mode) == "Convoy"
    assert str(domination.gameplay_mode) == "Domination"
    assert convoy.gameplay_mode.id == domination.gameplay_mode.id == 200
    assert not Match(game_play_mode_id=200).gameplay_mode.is_known


@pytest.mark.parametrize("code,name", [(1, "PC"), (2, "PlayStation"), (4, "Xbox"), ("4", "Xbox"), ("psn", "PlayStation")])
def test_verified_platform_codes(code, name):
    assert str(Platform(code)) == name
    assert Platform(code).id == code


def test_unknown_and_missing_codes_are_explicit_and_preserved():
    match = Match(map_id="99999", game_mode_id=999, game_play_mode_id=999, platform=3,
                  rank_level=999, season=999, hero_id=999)
    assert str(match.map) == "Unknown map"
    assert match.map.id == "99999"
    for ref in (match.map, match.game_mode, match.gameplay_mode, match.platform, match.rank, match.season_info):
        assert ref.is_known is False
        assert str(ref).startswith("Unknown ")
    assert str(match.hero) == "Unknown hero"
    assert Match({}).map is None
    assert Match({}).platform is None
    assert Match({}).game_mode is None
    assert Match({}).gameplay_mode is None
    assert Map(True).is_known is False
    assert Rank("2.5").is_known is False
    assert Season(21).is_known is False


def test_provider_names_can_resolve_new_maps_before_catalog_updates():
    match = Match(map_id=9999, map_name="New Map", map_mode_name="New Objective")
    assert match.map.name == "New Map"
    assert match.map.id == 9999
    assert match.map.is_known
    assert match.gameplay_mode.name == "New Objective"
    assert match.gameplay_mode.map_id == 9999


def test_mode_six_keeps_source_specific_labels_and_alternatives():
    assert GameMode(6, source="rivalsdata").name == "Duel"
    assert GameMode(6, source="rivalstracker").name == "Practice"
    assert not GameMode(6).is_known
    match = Match(game_mode_id=6, provider_metadata={"sources": ["rivalsdata", "rivalstracker"],
                  "selections": {"game_mode_id": {"source": "rivalstracker"}}})
    assert match.game_mode.name == "Practice"
    assert match.game_mode.alternatives.rivalsdata == "Duel"


def test_nested_references_keep_stats_and_round_trip_in_json():
    data = {"match_uid": "match-1", "map_id": "1288", "game_mode_id": 3, "platform": 4,
            "teams": [{"camp": 0, "players": [{"player_uid": "123", "name": "Example",
                "top_hero_id": 1016, "rank_level": 22, "os": 4,
                "heroes": [{"hero_id": 1016, "kills": 5, "accuracy_percent": 40}]}]}],
            "draft": [{"hero_id": 1011, "battle_side": 0}]}
    match = Match(data)
    player = match.teams[0].players[0]
    assert isinstance(player.top_hero, Character)
    assert player.top_hero.kills == 5
    assert player.hero is player.top_hero
    assert player.top_hero.accuracy_percent == 40
    assert str(player) == "Example"
    assert player.id == "123"
    assert str(player.rank_info) == "Eternity"
    assert str(player.platform_info) == "Xbox"
    assert str(match.teams[0]) == "Team 1"
    assert match.teams[0].id == 0
    assert str(match.draft[0].hero) == "Hulk"
    assert str(match.draft[0].team) == "Team 1"

    serialized = json.loads(json.dumps(match.to_dict(), allow_nan=False))
    assert serialized["map_id"] == "1288"
    assert serialized["platform_id"] == 4
    assert serialized["platform"]["name"] == "Xbox"
    assert serialized["map"]["name"] == "Hell's Heaven"
    restored = Match(serialized)
    assert isinstance(restored.platform, Platform)
    assert isinstance(restored.teams[0].players[0].top_hero, Character)
    assert restored.to_dict() == serialized
    assert match.raw["platform"] == 4
    assert "map" not in match.raw


def test_named_players_hero_and_rank_records_work_without_history():
    player = MatchPlayer(hero_id=1016, uid=123, name="Example")
    assert player.hero.name == "Loki"
    assert player.hero.id == 1016
    rank = RankRecord(rank_level=1, season=19)
    assert rank.rank_info.name == "Bronze 3"
    assert rank.season_info.name == "Season 9.5"


def test_winner_references_existing_team_and_draw_has_no_winner():
    match = Match(winner_camp=0, is_win=True, teams=[{"camp": 0}, {"camp": 1}])
    assert match.winner is match.teams[0]
    assert match.result == "Victory"
    assert Match(is_win=False).result == "Defeat"
    assert Match({}).result is None
    assert Match(winner_camp=12).result == "Draw"
    assert Match(winner_camp=12).winner is None
    assert isinstance(Match(winner_camp=1).winner, MatchTeam)


def test_provider_normalizers_preserve_reference_context():
    history = Match(rt_history({"match_uid": "match-1", "match_map_id": 1288,
                    "game_mode_id": 3, "game_play_mode_id": 200, "platform": 2}))
    assert history.map.name == "Hell's Heaven"
    assert history.platform.name == "PlayStation"
    rt = Match(rt_match({"match_uid": "match-1", "match_map_id": 1288,
                        "game_mode_id": 3, "game_play_mode_id": 200, "platform": 1}))
    assert rt.map.name == history.map.name
    tracker = Match(tracker_match({"attributes": {"id": "match-1", "mapId": 9999},
                   "metadata": {"mapName": "New Map", "mapModeName": "Domination",
                                "modeName": "Competitive"}}))
    assert tracker.map.name == "New Map"
    assert tracker.game_mode.name == "Competitive"
    assert tracker.game_mode.id is None
    assert tracker.gameplay_mode.name == "Domination"


def test_legacy_imports_expose_the_same_reference_classes():
    from rivalsdata import Map as LegacyMap
    from rivalsdata import Platform as LegacyPlatform

    assert LegacyMap is Map
    assert LegacyPlatform is Platform


def test_lazy_details_retain_history_map_context_when_detail_provider_omits_it():
    class Resource:
        def get(self, identifier, *, refresh):
            assert identifier == "match-1"
            assert refresh is False
            return result

    class Client:
        matches = Resource()

    result = Match(match_uid="match-1", game_mode_id=2, provider_metadata={"sources": ["rivalstracker"]})
    history = Match({"match_uid": "match-1", "map_id": 1288, "game_mode_id": 3,
                     "platform": 1, "provider_metadata": {"sources": ["rivalstracker"]}}, client=Client())
    before = result.to_dict()
    detail = history.get_details()
    assert detail.map.name == "Hell's Heaven"
    assert detail.platform.name == "PC"
    assert detail.game_mode.name == "Competitive"
    assert detail.provider_metadata.history_context.fields.map_id == 1288
    assert result.to_dict() == before


@pytest.mark.parametrize("placeholder", ["", " ", "-", "Unknown", "1288"])
def test_placeholder_provider_labels_do_not_hide_known_catalog_names(placeholder):
    match = Match(map_id=1288, map_name=placeholder, map_mode_name=placeholder)
    assert match.map.name == "Hell's Heaven"
    assert match.gameplay_mode.name == "Domination"
