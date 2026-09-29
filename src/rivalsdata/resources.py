"""Resource managers for public non-player and player-section endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import quote

from .models import (
    BanRecord,
    Character,
    CommBanInsights,
    CrosshairRecord,
    DataModel,
    Faction,
    FavoritePlayer,
    FavoritesResponse,
    HeroDetail,
    HeroLeaderboardResponse,
    HeroMeta,
    HeroStatsRecord,
    LeaderboardResponse,
    LeaverInsights,
    LiveGame,
    MapRecord,
    Match,
    MatchHistory,
    NameHistoryRecord,
    ProficiencyResponse,
    ProfileCard,
    PunishmentsPage,
    StatRecord,
    Teammate,
    TeamUpsResponse,
    TierListResponse,
    Top500Response,
    XPPage,
)
from .models import (
    PlayerPunishments as PlayerPunishmentsModel,
)


def _one(value: Any, model: type[DataModel] = DataModel) -> Any:
    return model(value) if isinstance(value, dict) else value


def _many(value: Any, model: type[DataModel] = StatRecord) -> Any:
    if isinstance(value, list):
        return [model(row) if isinstance(row, dict) else row for row in value]
    return _one(value)


class Leaderboards:
    """Global player leaderboard resource (``GET /leaderboards``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(
        self, *, limit: int = 100, skip: int = 0, season: int | None = None,
        platform: int | str | None = None,
    ) -> LeaderboardResponse:
        params: dict[str, Any] = {"limit": limit}
        if skip:
            params["skip"] = skip
        if season is not None:
            params["season"] = season
        if platform is not None:
            params["os"] = platform
        return _one(self._client._get_json("/leaderboards", params=params), LeaderboardResponse)


class HeroStats:
    """Aggregate hero tier-list, detail, trend, and leaderboard data."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def tier_list(
        self, *, platform: int | str = 1, rank: str = "grandmaster_plus"
    ) -> TierListResponse:
        return _one(self._client._get_json(
            "/stats/tierlist", params={"platform": platform, "rank": rank}
        ), TierListResponse)

    def get(self, hero_id: str | int) -> HeroDetail:
        return _one(self._client._get_json(f"/stats/heroes/{quote(str(hero_id))}"), HeroDetail)

    def meta(self, hero_id: str | int, *, range: int = 90) -> HeroMeta:
        if range not in (30, 90, 180):
            raise ValueError("range must be 30, 90, or 180 days")
        return _one(self._client._get_json(
            f"/stats/meta/{quote(str(hero_id))}", params={"range": f"{range}d"}
        ), HeroMeta)

    def leaderboard(self, hero_id: str | int, **filters: Any) -> HeroLeaderboardResponse:
        """Fetch a hero-specific leaderboard; filters pass through as query args."""
        params = {"hero": hero_id, **filters}
        return _one(self._client._get_json("/stats/leaderboards", params=params), HeroLeaderboardResponse)


class TeamUps:
    """Global team-up analytics (``GET /stats/teamups``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(self, *, platform: int | str = 1, rank: str = "grandmaster_plus") -> TeamUpsResponse:
        return _one(self._client._get_json(
            "/stats/teamups", params={"platform": platform, "rank": rank}
        ), TeamUpsResponse)


class Insights:
    """Public site-wide insights pages and their pagination metadata."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def punishments(self, *, kind: str = "login", cursor: str | None = None) -> PunishmentsPage:
        params: dict[str, Any] = {"kind": kind}
        if cursor:
            params["cursor"] = cursor
        return _one(self._client._get_json("/stats/punishments", params=params), PunishmentsPage)

    def xp(self, *, cursor: str | None = None) -> XPPage:
        params = {"cursor": cursor} if cursor else None
        return _one(self._client._get_json("/stats/xp", params=params), XPPage)

    def top_500(self, *, platform: int | str = 1) -> Top500Response:
        return _one(self._client._get_json("/stats/oaa", params={"os": platform}), Top500Response)

    def commbans(self, *, mode: str = "all") -> CommBanInsights:
        return _one(self._client._get_json("/stats/commbans", params={"mode": mode}), CommBanInsights)

    def leavers(self, *, mode: str = "all") -> LeaverInsights:
        return _one(self._client._get_json("/stats/leavers", params={"mode": mode}), LeaverInsights)


class Factions:
    """Faction pages (``GET /faction/{faction_id}``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, faction_id: str | int) -> Faction:
        return _one(self._client._get_json(f"/faction/{quote(str(faction_id))}"), Faction)


class Profiles:
    """Public profile-card pages (response schema is not fully mapped)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, uid_or_username: str | int) -> ProfileCard:
        value = str(uid_or_username).strip()
        if not value:
            raise ValueError("uid_or_username must not be empty")
        uid = value if value.isdecimal() else str(self._client.resolve_player(value)["uid"])
        return _one(self._client._get_json(
            f"/profiles/{uid}"
        ), ProfileCard)


class Favorites:
    """Fetch profile summaries for a supplied list of favorite UIDs."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(self, uids: list[str | int]) -> list[FavoritePlayer] | FavoritesResponse:
        result = self._client._post_json("/favorites", {"uids": [int(uid) for uid in uids]})
        if isinstance(result, list):
            return [FavoritePlayer(row) if isinstance(row, dict) else row for row in result]
        return _one(result, FavoritesResponse)


class PlayerResource:
    def __init__(self, client: Any, uid: int) -> None:
        self._client = client
        self.uid = uid

    def _post(self, path: str, **payload: Any) -> Any:
        return self._client._post_json(path, {"uid": self.uid, **payload})


class PlayerHeroes(PlayerResource):
    """Per-player hero summary rows from ``POST /player/heroes``."""

    def fetch(self, *, season: int | Literal["all"] | None = None) -> list[Character]:
        """Fetch hero summaries for one season or all seasons.

        ``season="all"`` uses the API's all-seasons selector (season ID -1).
        Omitting ``season`` keeps the endpoint's default behavior.
        """
        season_id = -1 if season == "all" else season
        payload = {"season": season_id} if season_id is not None else {}
        return _many(self._post("/player/heroes", **payload), Character)


class PlayerStats(PlayerResource):
    """Detailed per-player statistics tabs."""

    def heroes(self, *, season: int | None = None) -> list[HeroStatsRecord]:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/heroes", **payload), HeroStatsRecord)

    def maps(self, *, season: int | None = None) -> list[MapRecord]:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/maps", **payload), MapRecord)

    def bans(self, *, season: int | None = None) -> list[BanRecord]:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/bans", **payload), BanRecord)


class PlayerMatches(PlayerResource):
    """Player match-history pages."""

    def fetch(
        self, *, cursor: str | None = None, season: int | None = None,
        mode: str | None = None, hero: str | int | None = None,
        teammate: str | int | None = None, cached: bool = True,
    ) -> MatchHistory:
        payload: dict[str, Any] = {"cursor": cursor}
        for key, value in (("season", season), ("mode", mode), ("hero", hero), ("teammate", teammate)):
            if value is not None:
                payload[key] = value
        path = "/player/matches/cached" if cached else "/player/matches"
        result = self._post(path, **payload)
        return MatchHistory(result) if isinstance(result, dict) else result


class PlayerLiveGame(PlayerResource):
    """Current live match data for a player whose profile status is in-game.

    The site supplies the opaque match ID in the player's ``status.battle_id``
    field. A fresh player profile is needed to discover the current match.
    """

    def __init__(self, client: Any, player_data: dict[str, Any]) -> None:
        super().__init__(client, int(player_data["uid"]))
        self._player_data = player_data

    def fetch(self) -> LiveGame | None:
        """Fetch the current live match, or return ``None`` if out of game."""
        status = self._player_data.get("status")
        if not isinstance(status, Mapping):
            return None
        match_id = status.get("battle_id")
        if not match_id:
            return None
        return _one(self._client._post_json(
            "/live", {"match_id": str(match_id), "uid": self.uid}
        ), LiveGame)


class PlayerTeammates(PlayerResource):
    def fetch(self, *, season: int | None = None, mode: str | None = None) -> list[Teammate]:
        payload = {key: value for key, value in (("season", season), ("mode", mode)) if value is not None}
        return _many(self._post("/player/teammates", **payload), Teammate)


class PlayerCrosshairs(PlayerResource):
    def fetch(self) -> list[CrosshairRecord]:
        return _many(self._post("/player/crosshairs"), CrosshairRecord)


class PlayerProficiency(PlayerResource):
    def fetch(self) -> ProficiencyResponse:
        return _one(self._post("/player/proficiency"), ProficiencyResponse)


class PlayerPunishments(PlayerResource):
    def fetch(self) -> PlayerPunishmentsModel:
        return _one(self._post("/player/punishments"), PlayerPunishmentsModel)


class PlayerNameHistory(PlayerResource):
    def fetch(self) -> list[NameHistoryRecord]:
        return _many(self._post("/player/name-history"), NameHistoryRecord)


class Matches:
    """Match detail endpoint. The upstream match identifier format is opaque."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, match_id: str | int) -> Match:
        result = self._client._post_json("/match", {"match_id": str(match_id)})
        return Match(result) if isinstance(result, dict) else result
