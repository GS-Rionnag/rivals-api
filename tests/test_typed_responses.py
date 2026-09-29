from rivalsdata.models import (
    Character,
    DraftEntry,
    HeroMeta,
    Match,
    MatchPlayer,
    MatchTeam,
    Player,
    ProficiencyResponse,
    TeamUpRecord,
    TeamUpsResponse,
    TierListResponse,
)
from rivalsdata.resources import Favorites, HeroStats


class FakeClient:
    def __init__(self) -> None:
        self.path = ""
        self.params = None
        self.payload = None

    def _get_json(self, path, *, params=None):
        self.path, self.params = path, params
        return {"hero_id": 1011, "range": "90d", "points": [{"ts": 1, "games": 2}]}

    def _post_json(self, path, payload):
        self.path, self.payload = path, payload
        if path == "/live":
            return {"players": {"1": {"uid": 123, "name": "Example"}}, "team_avg_rank": {"1": 10}}
        return [{"aid": "11001_123", "name": "Example"}]


def test_nested_match_and_proficiency_models() -> None:
    match = Match({
        "match_uid": "match-1",
        "draft": [{"hero_id": 1011, "is_pick": True}],
        "teams": [{"camp": 1, "players": [{
            "player_uid": "123", "heroes": [{"hero_id": 1011, "play_time": 42.0}]
        }]}],
    })
    proficiency = ProficiencyResponse({
        "11001_123": {"hero_proficiency_infos": {
            "1011": {"proficiency_level": 3, "proficiency_point": 120}
        }}
    })

    assert isinstance(match.draft[0], DraftEntry)
    assert isinstance(match.teams[0], MatchTeam)
    assert isinstance(match.teams[0].players[0], MatchPlayer)
    assert isinstance(match.teams[0].players[0].heroes[0], Character)
    assert proficiency.accounts["11001_123"].hero_proficiency_infos["1011"].proficiency_point == 120
    assert match.to_dict()["teams"][0]["players"][0]["heroes"][0]["hero_id"] == 1011
    assert isinstance(match.raw["teams"][0], dict)
    assert isinstance(proficiency.raw["11001_123"], dict)


def test_global_envelopes_wrap_rows() -> None:
    tier = TierListResponse({"heroes": [{"hero_id": 1011, "picks": 5}]})
    teamups = TeamUpsResponse({"heroes": {"1011": {"1": {"bond_id": 7}}}})

    assert isinstance(tier.heroes[0], Character)
    assert isinstance(teamups.heroes["1011"]["1"], TeamUpRecord)


def test_corrected_request_formats() -> None:
    client = FakeClient()

    meta = HeroStats(client).meta(1011, range=90)
    assert isinstance(meta, HeroMeta)
    assert client.params == {"range": "90d"}

    favorites = Favorites(client).fetch(["123"])
    assert client.payload == {"uids": [123]}
    assert favorites[0].aid == "11001_123"


def test_typed_profile_keeps_rank_and_live_game_access() -> None:
    client = FakeClient()
    player = Player({
        "uid": "123",
        "faction": {"id": "team-1", "name": "Example"},
        "status": {"battle_id": "match-1"},
        "rank_game_season": {"1001020": {"battle_count": 10, "win_count": 6}},
    }, client)

    assert player.faction.name == "Example"
    assert player.win_rate == 60
    assert player.live_game.fetch().players["1"].name == "Example"
    assert client.payload == {"match_id": "match-1", "uid": 123}
