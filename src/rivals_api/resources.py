"""Resource managers for public non-player and player-section endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import quote

from .exceptions import RivalsDataError
from .hero_ids import hero_class, hero_id
from .models import (
    BanRecord,
    Character,
    ClassStatsResponse,
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
from .normalize import merge, merge_match, mode_id, rt_match, tracker_match


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
        result = self._client._get_json(
            "/stats/tierlist", params={"platform": platform, "rank": rank}
        )
        if getattr(self._client, "enrich", False):
            # Keep raw rank buckets separate; provider ranks/platform samples
            # are not equivalent to RD's selected tier-list scope.
            extra = self._client._optional_provider("rt", "/heroes/stats")
            if extra:
                result = {**result, "additional_meta": extra,
                          "additional_meta_scope": {"source": "rivalstracker",
                                                    "rank_buckets": "provider_defined"}}
        return _one(result, TierListResponse)

    def get(self, hero_id: str | int) -> HeroDetail:
        result = self._client._get_json(f"/stats/heroes/{quote(str(hero_id))}")
        if getattr(self._client, "enrich", False):
            result = {**result, "reference": self._client.analytics.hero_reference(hero_id).data}
        return _one(result, HeroDetail)

    def meta(self, hero_id: str | int, *, range: int = 90) -> HeroMeta:
        if range not in (30, 90, 180):
            raise ValueError("range must be 30, 90, or 180 days")
        result = self._client._get_json(
            f"/stats/meta/{quote(str(hero_id))}", params={"range": f"{range}d"}
        )
        if getattr(self._client, "enrich", False):
            extra = self._client._optional_provider("rt", f"/hero-stats-history/{quote(str(hero_id))}",
                                                   params={"days": range, "platform": "pc"})
            if extra:
                result = {**result, "combat_history": extra,
                          "combat_history_scope": {"rank": "celestial+", "platform": "pc"}}
        return _one(result, HeroMeta)

    def matchups(self, hero_id: str | int | None = None) -> DataModel:
        return self._client.analytics.hero_matchups(hero_id)

    def reference(self, hero_id: str | int | None = None) -> DataModel:
        return self._client.analytics.hero_reference(hero_id)

    def history(self, hero_id: str | int, *, days: int = 30,
                platform: str = "pc") -> DataModel:
        return self._client.analytics.hero_history(hero_id, days=days, platform=platform)

    def season_stats(self, *, season: int | None = None) -> DataModel:
        return self._client.analytics.hero_stats(season=season)

    def leaderboard(self, hero_id: str | int, **filters: Any) -> HeroLeaderboardResponse:
        """Fetch a hero-specific leaderboard; filters pass through as query args."""
        params = {"hero": hero_id, **filters}
        result = self._client._get_json("/stats/leaderboards", params=params)
        if getattr(self._client, "enrich", False):
            extra = self._client._optional_provider("rt", f"/hero-players/{quote(str(hero_id))}",
                                                   params={"season": filters.get("season"),
                                                           "device": filters.get("platform", 1)})
            if extra:
                result = {**result, "additional_players": extra,
                          "additional_players_scope": {"source": "rivalstracker",
                                                       "filters": "provider_default_or_explicit_season_device"}}
        return _one(result, HeroLeaderboardResponse)


class TeamUps:
    """Global team-up analytics (``GET /stats/teamups``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(self, *, platform: int | str = 1, rank: str = "grandmaster_plus") -> TeamUpsResponse:
        result = self._client._get_json(
            "/stats/teamups", params={"platform": platform, "rank": rank}
        )
        if getattr(self._client, "enrich", False):
            extra = self._client._optional_provider("rt", "/heroes/stats")
            if extra:
                result = {**result, "additional_teamups": extra.get("teamups", []),
                          "additional_teamups_scope": {"source": "rivalstracker",
                                                        "rank_buckets": "provider_defined"}}
        return _one(result, TeamUpsResponse)

    def compositions(self) -> DataModel:
        return self._client.analytics.team_compositions()


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

    @property
    def analytics(self):
        from .extensions import PlayerAnalytics

        return PlayerAnalytics(self._client, self.uid)


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

    def heroes(
        self, *, mode: Literal["competitive", "quickplay"],
        season: int | Literal["all"] | None = None,
    ) -> list[HeroStatsRecord]:
        """Fetch heroes for a required mode, in the website's most-played order.

        The source supplies both modes together. This method keeps only heroes
        with the selected mode's data, removes the other mode, and sorts by
        selected-mode games descending. Ties retain the source order.
        Each row includes ``rank`` (the source's hero leaderboard position,
        also shown in the left-hand profile card), or None when unavailable.
        ``season="all"`` sends the API's all-seasons selector (-1). Omitting
        ``season`` preserves the endpoint default.
        """
        if mode not in ("competitive", "quickplay"):
            raise ValueError("mode must be competitive or quickplay")
        heroes = [hero for hero in self._hero_records(season=season, selected_mode=mode)
                  if hero.get(mode) is not None]
        heroes.sort(key=lambda hero: hero[mode].get("games", 0) or 0, reverse=True)
        other_mode = "quickplay" if mode == "competitive" else "competitive"
        return [HeroStatsRecord({key: value for key, value in hero.raw.items()
                                 if key != other_mode}, mode=mode) for hero in heroes]

    def _hero_records(
        self, *, season: int | Literal["all"] | None = None, selected_mode: str | None = None
    ) -> list[HeroStatsRecord]:
        """Fetch both upstream modes for class aggregation and hero filtering."""
        season_id = -1 if season == "all" else season
        payload = {"season": season_id} if season_id is not None else {}
        original_error = None
        try:
            result = self._post("/player/stats/heroes", **payload)
        except RivalsDataError as exc:
            if not getattr(self._client, "enrich", False):
                raise
            original_error = exc
            result = []
        if getattr(self._client, "enrich", False):
            for row in result:
                for mode in ("competitive", "quickplay"):
                    if isinstance(row.get(mode), dict):
                        row[mode].setdefault("provider_metadata", {"sources": ["rivalsdata"]})
            # RT's lifetime selector is not established; retain the proven RD
            # all-seasons contract instead of blending current-season data.
            body = self._client._rt_player(self.uid, season_id) if season_id != -1 else None
            if body:
                by_id = {str(row["hero_id"]): row for row in result}
                for mode, key in (("competitive", "heroes_ranked"), ("quickplay", "heroes_unranked")):
                    for identifier, data in body.get(key, {}).items():
                        if not data.get("matches"):
                            continue
                        supplemental = {"games": data.get("matches"), "wins": data.get("win"),
                                        "losses": data["matches"] - data.get("win", 0),
                                        "mvps": data.get("mvp"), "svps": data.get("svp"),
                                        "play_time": data.get("play_time"), "kills": data.get("kills"),
                                        "deaths": data.get("deaths"), "assists": data.get("assists"),
                                        "damage": data.get("damage"), "healing": data.get("heal"),
                                        "damage_taken": data.get("damage_taken")}
                        row = by_id.setdefault(identifier, {"hero_id": int(identifier)})
                        scope = {"uid": self.uid, "hero_id": int(identifier),
                                 "season": season_id, "mode": mode,
                                 "counts_basis": "hero_participation"}
                        row[mode] = merge(row.get(mode, {}), supplemental, "rivalstracker",
                                          primary_context={"kind": "career", "scope": scope},
                                          context={"kind": "career", "scope": scope})
                result = list(by_id.values())
            # Different mode/season scopes are queried separately. Tracker's
            # fractional participation counts are never treated as unique games.
            from .normalize import tracker_stats

            by_id = {str(row["hero_id"]): row for row in result}
            try:
                path = self._client._tracker_path(self.uid) + "/segments/career"
            except RivalsDataError:
                path = None
            for mode in ([selected_mode] if selected_mode else ["competitive", "quickplay"]):
                params = {"mode": "quick-match" if mode == "quickplay" else mode}
                if season_id not in (None, -1):
                    params["season"] = season_id
                # Without an explicit season, enrich RT/RD only when Tracker's
                # own default-season contract is selected as well.
                segments = self._client._optional_provider("tracker", path, params=params) if path and season_id != -1 else None
                for segment in segments or []:
                    if segment.get("type") != "hero":
                        continue
                    attributes = segment.get("attributes", {})
                    if (attributes.get("mode") != params["mode"]
                            or season_id is not None and str(attributes.get("season")) != str(season_id)):
                        continue
                    identifier = str(attributes.get("heroId", ""))
                    extras = tracker_stats(segment)
                    if isinstance(extras.get("matchesPlayed"), (int, float)) and isinstance(extras.get("matchesWon"), (int, float)):
                        extras.update(games=extras["matchesPlayed"], wins=extras["matchesWon"],
                                      losses=extras["matchesPlayed"] - extras["matchesWon"])
                    if identifier not in by_id or not by_id[identifier].get(mode):
                        if not original_error:
                            continue
                        count = extras.get("matchesPlayed")
                        wins = extras.get("matchesWon")
                        if not identifier.isdecimal() or not isinstance(count, (int, float)) or not isinstance(wins, (int, float)):
                            continue
                        by_id.setdefault(identifier, {"hero_id": int(identifier)})[mode] = {
                            "games": count, "wins": wins, "losses": count - wins,
                            "counts_basis": "tracker_hero_participation", "unique_matches_verified": False}
                    scope = {"uid": self.uid, "hero_id": int(identifier),
                             "season": attributes.get("season"), "mode": mode,
                             "counts_basis": "hero_participation"}
                    by_id[identifier][mode] = merge(by_id[identifier][mode], extras, "tracker",
                                                    context={"kind": "career", "scope": scope})
            result = list(by_id.values())
        if original_error and not result:
            raise original_error
        return _many(result, HeroStatsRecord)

    def career(self, *, season: int | Literal["all"] | None = None,
               mode: str = "all") -> DataModel:
        """Detailed Tracker career, including raw combat stats and percentiles."""
        return self.analytics.career(season=season, mode=mode)

    def matchups(self, *, season: int | None = None) -> DataModel:
        return self.analytics.matchups(season=season)

    def classes(
        self, *, season: int | Literal["all"] | None = None
    ) -> ClassStatsResponse:
        """Sum hero records by tank/support/dps, separately for each mode.

        Supply a season ID or ``season="all"`` for combined all-seasons totals.
        Omitting ``season`` preserves the endpoint default.
        Win rate uses total wins / (wins + losses), not the average of hero
        percentages. Counts are summed upstream hero records. The upstream
        attribution rule for hero switches is unknown, so distinct match
        counts cannot be established from these rows. ``metadata`` describes
        the calculation and requested season scope.
        Unknown roles and incomplete win/loss rows are listed in ``excluded``.
        """
        groups = {
            name: {"player_class": name, "role": role, "hero_ids": [],
                   "competitive": [], "quickplay": []}
            for name, role in (("tank", "Vanguard"), ("support", "Strategist"),
                               ("dps", "Duelist"))
        }
        excluded = []
        for hero in self._hero_records(season=season):
            identifier = hero.get("hero_id")
            name = hero_class(identifier)
            if name is None:
                excluded.append({"hero_id": identifier, "reason": "unknown_class"})
                continue
            group = groups[name]
            group["hero_ids"].append(identifier)
            for mode in ("competitive", "quickplay"):
                row = hero.get(mode)
                if row is None:
                    continue
                counts = [row.get(key) for key in ("wins", "losses")]
                if any(not isinstance(value, (int, float)) or isinstance(value, bool)
                       or value < 0 for value in counts):
                    excluded.append({"hero_id": identifier, "mode": mode,
                                     "reason": "missing_or_invalid_win_loss_counts"})
                    continue
                group[mode].append(row)
        for group in groups.values():
            for mode in ("competitive", "quickplay"):
                rows = group[mode]
                totals = {key: sum(row[key] for row in rows)
                          for key in ("wins", "losses")}
                totals["games"] = sum(
                    row.get("games") if isinstance(row.get("games"), (int, float))
                    else row["wins"] + row["losses"] for row in rows
                )
                for key in ("mvps", "svps"):
                    if rows and all(isinstance(row.get(key), (int, float))
                                    for row in rows):
                        totals[key] = sum(row[key] for row in rows)
                for key in ("play_time", "kills", "deaths", "assists", "damage",
                            "healing", "damage_taken"):
                    if rows and all(isinstance(row.get(key), (int, float)) for row in rows):
                        totals[key] = sum(row[key] for row in rows)
                total = totals["wins"] + totals["losses"]
                totals["win_rate"] = round(totals["wins"] * 100 / total) if total else None
                group[mode] = totals
        all_seasons = season in ("all", -1)
        warnings = [
            ("Hero records may overlap within a match. Class totals must not "
             "be used to calculate the player's overall match win rate.")
        ]
        if all_seasons:
            warnings.append(
                "All-seasons results cover the records returned by the source; "
                "complete lifetime coverage is not verified."
            )
        if excluded:
            warnings.append(
                "Some hero or mode records were excluded; see excluded for details."
            )
        metadata = {
            "source": "/player/stats/heroes",
            "counts_basis": "summed_hero_records",
            "win_rate_formula": "wins / (wins + losses) * 100",
            "unique_matches_verified": False,
            "hero_switch_attribution": "unknown",
            "season": "all" if all_seasons else season,
            "season_scope": "all" if all_seasons else (
                "endpoint_default" if season is None else "season"
            ),
            "warnings": warnings,
        }
        return ClassStatsResponse({"classes": list(groups.values()), "excluded": excluded,
                                   "metadata": metadata})

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
        if hero is not None:
            identifier = int(hero) if str(hero).isdecimal() else hero_id(str(hero))
            if identifier is None:
                raise ValueError("hero must be a known hero name or numeric ID")
            hero = identifier
        if teammate is not None:
            teammate = int(teammate) if str(teammate).isdecimal() else int(
                self._client.resolve_player(str(teammate))["uid"])
        payload: dict[str, Any] = {"cursor": cursor}
        for key, value in (("season", season), ("mode", mode), ("hero", hero), ("teammate", teammate)):
            if value is not None:
                payload[key] = value
        path = "/player/matches/cached" if cached else "/player/matches"
        if getattr(self._client, "enrich", False):
            from .history import fetch_history

            return fetch_history(self, cursor=cursor, season=season, mode=mode,
                                 hero=hero, teammate=teammate, cached=cached)
        if mode is not None:
            payload["mode"] = mode_id(mode)
        result = self._post(path, **payload)
        return MatchHistory(result) if isinstance(result, dict) else result

    def iter(self, **filters: Any):
        """Iterate history until all providers are exhausted (including empty pages)."""
        cursor = filters.pop("cursor", None)
        while True:
            page = self.fetch(cursor=cursor, **filters)
            yield from page.matches
            next_cursor = page.get("next_cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor


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
        result = self._post("/player/teammates", **payload)
        if getattr(self._client, "enrich", False):
            query_mode = "quick-match" if mode == "quickplay" else (mode or "all")
            extra = self._client._optional_provider("tracker", self._client._tracker_path(self.uid) + "/aggregated",
                                                    params={"season": season, "mode": query_mode,
                                                            "filter": "encounters", "localOffset": 0})
            if extra:
                by_name = {row.get("platformInfo", {}).get("platformUserIdentifier"): row
                           for row in extra.get("teammates", [])}
                result = [merge(row, {"last_encounter": by_name[row.get("name")].get("metadata", {}).get("lastMatchTimestamp"),
                                      "encounter_stats": by_name[row.get("name")].get("stats", {})}, "tracker")
                          if row.get("name") in by_name else row for row in result]
        return _many(result, Teammate)

    def encounters(self, *, season: int | None = None, mode: str = "all",
                   local_offset: int = 0) -> DataModel:
        return self.analytics.encounters(season=season, mode=mode, local_offset=local_offset)


class PlayerCrosshairs(PlayerResource):
    def fetch(self) -> list[CrosshairRecord]:
        return _many(self._post("/player/crosshairs"), CrosshairRecord)


class PlayerProficiency(PlayerResource):
    def fetch(self) -> ProficiencyResponse:
        return _one(self._post("/player/proficiency"), ProficiencyResponse)


class PlayerPunishments(PlayerResource):
    def fetch(self) -> PlayerPunishmentsModel:
        return _one(self._post("/player/punishments"), PlayerPunishmentsModel)

    def history(self) -> DataModel:
        return self.analytics.punishment_history()


class PlayerNameHistory(PlayerResource):
    def fetch(self) -> list[NameHistoryRecord]:
        result = self._post("/player/name-history")
        if getattr(self._client, "enrich", False):
            body = self._client._optional_provider("rt", f"/player/{self.uid}/identity-cosmetics")
            if body:
                names = {row["name"]: row for row in result}
                for row in body.get("names", []):
                    name = row.get("name")
                    if name:
                        names[name] = merge(names.get(name, {"name": name}), row, "rivalstracker")
                result = list(names.values())
        return _many(result, NameHistoryRecord)

    def events(self) -> DataModel:
        data = self.analytics.cosmetics()
        return DataModel({"data": data.data.get("name_changes", []), "source": data.source})


class Matches:
    """Match detail endpoint. The upstream match identifier format is opaque."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, match_id: str | int) -> Match:
        try:
            result = self._client._post_json("/match", {"match_id": str(match_id)})
            if getattr(self._client, "enrich", False) and isinstance(result, dict):
                result.setdefault("provider_metadata", {"sources": ["rivalsdata"]})
                result["provider_metadata"].setdefault("evidence", {})["rivalsdata"] = {
                    "kind": "match_detail", "complete": bool(result.get("teams")),
                    "scope": {"match_uid": str(match_id)}}
        except RivalsDataError:
            if not getattr(self._client, "enrich", False):
                raise
            result = {}
        if getattr(self._client, "enrich", False):
            rt = self._client._optional_provider("rt", f"/matches/{quote(str(match_id), safe='')}")
            if rt and rt.get("match_uid"):
                result = merge_match(result, rt_match(rt), "rivalstracker")
            tracker = self._client._optional_provider(
                "tracker", f"/api/v2/marvel-rivals/standard/matches/{quote(str(match_id), safe='')}")
            if tracker and tracker.get("attributes", {}).get("id"):
                result = merge_match(result, tracker_match(tracker), "tracker")
            if not result.get("match_uid"):
                raise RivalsDataError("No provider returned this match")
        return Match(result) if isinstance(result, dict) else result
