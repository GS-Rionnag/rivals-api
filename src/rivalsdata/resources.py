"""Resource managers for public non-player and player-section endpoints."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .models import DataModel, StatRecord


def _one(value: Any) -> Any:
    return DataModel(value) if isinstance(value, dict) else value


def _many(value: Any) -> Any:
    if isinstance(value, list):
        return [StatRecord(row) if isinstance(row, dict) else row for row in value]
    return _one(value)


class Leaderboards:
    """Global player leaderboard resource (``GET /leaderboards``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(
        self, *, limit: int = 100, skip: int = 0, season: int | None = None,
        platform: int | str | None = None,
    ) -> DataModel | list[Any]:
        params: dict[str, Any] = {"limit": limit}
        if skip:
            params["skip"] = skip
        if season is not None:
            params["season"] = season
        if platform is not None:
            params["os"] = platform
        return _one(self._client._get_json("/leaderboards", params=params))


class HeroStats:
    """Aggregate hero tier-list, detail, trend, and leaderboard data."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def tier_list(
        self, *, platform: int | str = 1, rank: str = "grandmaster_plus"
    ) -> Any:
        return _many(self._client._get_json(
            "/stats/tierlist", params={"platform": platform, "rank": rank}
        ))

    def get(self, hero_id: str | int) -> Any:
        return _one(self._client._get_json(f"/stats/heroes/{quote(str(hero_id))}"))

    def meta(self, hero_id: str | int, *, range: int = 90) -> Any:
        if range not in (30, 90, 180):
            raise ValueError("range must be 30, 90, or 180 days")
        return _one(self._client._get_json(
            f"/stats/meta/{quote(str(hero_id))}", params={"range": range}
        ))

    def leaderboard(self, hero_id: str | int, **filters: Any) -> Any:
        """Fetch a hero-specific leaderboard; filters pass through as query args."""
        params = {"hero": hero_id, **filters}
        return _many(self._client._get_json("/stats/leaderboards", params=params))


class TeamUps:
    """Global team-up analytics (``GET /stats/teamups``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(self, *, platform: int | str = 1, rank: str = "grandmaster_plus") -> Any:
        return _many(self._client._get_json(
            "/stats/teamups", params={"platform": platform, "rank": rank}
        ))


class Insights:
    """Public site-wide insights pages and their pagination metadata."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def punishments(self, *, kind: str = "login", cursor: str | None = None) -> Any:
        params: dict[str, Any] = {"kind": kind}
        if cursor:
            params["cursor"] = cursor
        return _one(self._client._get_json("/stats/punishments", params=params))

    def xp(self, *, cursor: str | None = None) -> Any:
        params = {"cursor": cursor} if cursor else None
        return _one(self._client._get_json("/stats/xp", params=params))

    def top_500(self, *, platform: int | str = 1) -> Any:
        return _one(self._client._get_json("/stats/oaa", params={"os": platform}))

    def commbans(self, *, mode: str = "all") -> Any:
        return _one(self._client._get_json("/stats/commbans", params={"mode": mode}))

    def leavers(self, *, mode: str = "all") -> Any:
        return _one(self._client._get_json("/stats/leavers", params={"mode": mode}))


class Factions:
    """Faction pages (``GET /faction/{faction_id}``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, faction_id: str | int) -> Any:
        return _one(self._client._get_json(f"/faction/{quote(str(faction_id))}"))


class Profiles:
    """Public profile-card pages (response schema is not fully mapped)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, username: str) -> Any:
        if not username.strip():
            raise ValueError("username must not be empty")
        return _one(self._client._get_json(
            f"/profiles/{quote(username.strip(), safe='')}"
        ))


class Favorites:
    """Fetch profile summaries for a supplied list of favorite UIDs."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(self, uids: list[str | int]) -> Any:
        return _many(self._client._post_json("/favorites", {"uids": [str(uid) for uid in uids]}))


class PlayerResource:
    def __init__(self, client: Any, uid: int) -> None:
        self._client = client
        self.uid = uid

    def _post(self, path: str, **payload: Any) -> Any:
        return self._client._post_json(path, {"uid": self.uid, **payload})


class PlayerHeroes(PlayerResource):
    """Per-player hero summary rows from ``POST /player/heroes``."""

    def fetch(self, *, season: int | None = None) -> Any:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/heroes", **payload))


class PlayerStats(PlayerResource):
    """Detailed per-player statistics tabs."""

    def heroes(self, *, season: int | None = None) -> Any:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/heroes", **payload))

    def maps(self, *, season: int | None = None) -> Any:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/maps", **payload))

    def bans(self, *, season: int | None = None) -> Any:
        payload = {"season": season} if season is not None else {}
        return _many(self._post("/player/stats/bans", **payload))


class PlayerMatches(PlayerResource):
    """Player match-history pages."""

    def fetch(
        self, *, cursor: str | None = None, season: int | None = None,
        mode: str | None = None, hero: str | int | None = None,
        teammate: str | int | None = None, cached: bool = True,
    ) -> Any:
        payload: dict[str, Any] = {"cursor": cursor}
        for key, value in (("season", season), ("mode", mode), ("hero", hero), ("teammate", teammate)):
            if value is not None:
                payload[key] = value
        path = "/player/matches/cached" if cached else "/player/matches"
        return _one(self._post(path, **payload))


class PlayerLiveGame(PlayerResource):
    """Current live match data for a player whose profile status is in-game.

    The site supplies the opaque match ID in the player's ``status.battle_id``
    field. A fresh player profile is needed to discover the current match.
    """

    def __init__(self, client: Any, player_data: dict[str, Any]) -> None:
        super().__init__(client, int(player_data["uid"]))
        self._player_data = player_data

    def fetch(self) -> DataModel | None:
        """Fetch the current live match, or return ``None`` if out of game."""
        status = self._player_data.get("status")
        if not isinstance(status, dict):
            return None
        match_id = status.get("battle_id")
        if not match_id:
            return None
        return _one(self._client._post_json(
            "/live", {"match_id": str(match_id), "uid": self.uid}
        ))


class PlayerTeammates(PlayerResource):
    def fetch(self, *, season: int | None = None, mode: str | None = None) -> Any:
        payload = {key: value for key, value in (("season", season), ("mode", mode)) if value is not None}
        return _many(self._post("/player/teammates", **payload))


class PlayerCrosshairs(PlayerResource):
    def fetch(self) -> Any:
        return _many(self._post("/player/crosshairs"))


class PlayerProficiency(PlayerResource):
    def fetch(self) -> Any:
        return _one(self._post("/player/proficiency"))


class PlayerPunishments(PlayerResource):
    def fetch(self) -> Any:
        return _one(self._post("/player/punishments"))


class PlayerNameHistory(PlayerResource):
    def fetch(self) -> Any:
        return _many(self._post("/player/name-history"))


class Matches:
    """Match detail endpoint. The upstream match identifier format is opaque."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, match_id: str | int) -> Any:
        return _one(self._client._post_json("/match", {"match_id": str(match_id)}))
