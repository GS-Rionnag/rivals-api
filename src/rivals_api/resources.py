"""Resource managers for public non-player and player-section endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import quote

from .exceptions import RivalsDataError
from .hero_ids import hero_class, hero_id, hero_name
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
from .normalize import merge, mode_id, timestamp


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

    def fetch(self, *, season: int | Literal["all"] | None = None,
              mode: Literal["competitive", "quickplay", "all"] = "all") -> list[HeroStatsRecord]:
        """List match-attributed heroes; all includes Competitive and Quickplay."""
        return PlayerStats(self._client, self.uid).heroes(season=season, mode=mode)

    def summary(self, *, season: int | Literal["all"] | None = None) -> list[Character]:
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
        self, *, mode: Literal["competitive", "quickplay", "all"] = "all",
        season: int | Literal["all"] | None = None,
    ) -> list[HeroStatsRecord]:
        """Canonical hero records: one result for the longest-played hero per match.

        No summary fallback is used for attribution. Each row includes coverage
        metadata; use hero_win_rates() to inspect coverage even for an empty list.
        """
        result = self.hero_win_rates(mode=mode, season=season)
        return [HeroStatsRecord({**row.to_dict(), mode: row.to_dict(), "mode": mode,
                                 "provider_metadata": result.metadata.to_dict()})
                for row in result.data]

    def win_rate(self, *, mode: Literal["competitive", "quickplay", "all"] = "all",
                 season: int | Literal["all"] | None = None) -> DataModel:
        """Select intact season career counts and check them against match history.

        Defaults to the current season and Competitive plus Quickplay. History
        fallback and unresolved provider disagreements are explicit in metadata.
        """
        from .season_rates import calculate

        return DataModel(calculate(self, season=season, mode=mode))

    def hero_win_rates(self, *, mode: Literal["competitive", "quickplay", "all"] = "all",
                       season: int | Literal["all"] | None = None) -> DataModel:
        from .attribution import calculate

        result = calculate(self, season=season, mode=mode)
        return DataModel({"data": result["heroes"], "metadata": result["metadata"]})

    def class_win_rates(self, *, mode: Literal["competitive", "quickplay", "all"] = "all",
                        season: int | Literal["all"] | None = None) -> DataModel:
        from .attribution import calculate

        result = calculate(self, season=season, mode=mode)
        return DataModel({"data": result["classes"], "metadata": result["metadata"]})

    def summary_heroes(
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
                        row[mode] = merge(row.get(mode) or {}, supplemental, "rivalstracker",
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
                        count = extras.get("matchesPlayed")
                        wins = extras.get("matchesWon")
                        if not identifier.isdecimal() or not isinstance(count, (int, float)) or not isinstance(wins, (int, float)):
                            continue
                        by_id.setdefault(identifier, {"hero_id": int(identifier)})[mode] = {
                            "games": count, "wins": wins, "losses": count - wins,
                            "counts_basis": "tracker_hero_participation", "unique_matches_verified": False,
                            "provider_metadata": {"sources": ["tracker"], "evidence": {
                                "tracker": {"kind": "career", "scope": {
                                    "uid": self.uid, "hero_id": int(identifier),
                                    "season": attributes.get("season"), "mode": mode,
                                    "counts_basis": "hero_participation"}}}}}
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
        self, *, season: int | Literal["all"] | None = None,
        mode: Literal["competitive", "quickplay", "all"] = "all",
    ) -> ClassStatsResponse:
        """Class results use each match's longest-played hero, once per match."""
        result = self.class_win_rates(season=season, mode=mode)
        return ClassStatsResponse({
            "classes": [{**row.to_dict(), mode: row.to_dict()} for row in result.data],
            "excluded": result.metadata.unresolved,
            "metadata": result.metadata.to_dict()})

    def summary_classes(
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
        self, *, limit: int | Literal["all"], cursor: str | None = None,
        season: int | None = None,
        mode: str | None = None, hero: str | int | None = None,
        teammate: str | int | None = None, cached: bool = True,
    ) -> MatchHistory:
        if limit != "all" and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise ValueError("limit must be a positive integer or 'all'")
        if hero is not None:
            identifier = int(hero) if str(hero).isdecimal() else hero_id(str(hero))
            if identifier is None:
                raise ValueError("hero must be a known hero name or numeric ID")
            hero = identifier
        if teammate is not None:
            teammate = int(teammate) if str(teammate).isdecimal() else int(
                self._client.resolve_player(str(teammate))["uid"])
        include_rt = bool(getattr(self._client, "enrich", False))
        from .history import fetch_history

        filters = {"season": season, "mode": mode, "hero": hero,
                   "teammate": teammate, "cached": cached, "include_rt": include_rt}
        if limit != "all":
            return fetch_history(self, cursor=cursor, limit=limit, **filters)

        rows: dict[str, dict[str, Any]] = {}
        sources: set[str] = set()
        errors: list[dict[str, str]] = []
        page_cursor = cursor
        seen_cursors: set[str] = set()
        primary: dict[str, Any] = {}
        while True:
            page = fetch_history(self, cursor=page_cursor, limit=None, **filters)
            primary = page.to_dict()
            for match in page.matches:
                row = match.to_dict()
                match_id = row.get("match_uid")
                if match_id is not None:
                    rows.setdefault(str(match_id), row)
            metadata = page.get("provider_metadata", {})
            sources.update(metadata.get("sources", []))
            errors.extend(metadata.get("errors", []))
            next_cursor = page.get("next_cursor")
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            page_cursor = next_cursor

        ordered = sorted(rows.values(), key=lambda row: timestamp(row.get("timestamp")), reverse=True)
        result = MatchHistory({**primary, "matches": ordered, "next_cursor": None,
                               "has_more": False, "source": "combined" if include_rt else "rivalsdata",
                               "provider_metadata": {"sources": sorted(sources), "errors": errors,
                                                     "scope": {key: value for key, value in filters.items()
                                                               if value is not None},
                                                     "ordering": "descending"}}, client=self._client)
        if cursor is None:
            cache_key = (self.uid, season, mode, str(hero) if hero is not None else None,
                         str(teammate) if teammate is not None else None, cached)
            self._client._match_history_cache.pop(cache_key, None)
            self._client._match_history_cache[cache_key] = {
                "matches": [row.to_dict() for row in result.matches],
                "sources": sorted(sources), "complete": not errors,
            }
            while len(self._client._match_history_cache) > 16:
                self._client._match_history_cache.pop(next(iter(self._client._match_history_cache)))
        return result

    def iter(self, **filters: Any):
        """Iterate all history after fetching every available page."""
        yield from self.fetch(limit="all", **filters).matches

    def fetch_win_rate(
        self, *, method: Literal["estimate", "exact", "cached"] | None = None,
        season: int | Literal["all"] | None = None,
        mode: Literal["competitive", "quickplay", "all"] = "all",
        hero: str | int | None = None, teammate: str | int | None = None,
        cached: bool = True,
    ) -> DataModel:
        """Select season records automatically; method is a legacy override.

        ``estimate`` is fast and averages the current competitive win rates
        reported by RivalsData and RivalsTracker. ``exact`` traverses all
        matching history pages. ``cached`` performs no requests and requires a
        prior complete, unfiltered ``fetch(limit="all")`` on this client.
        """
        if method is None:
            if hero is not None or teammate is not None:
                raise ValueError("Season win rate does not accept hero/teammate filters; use the hero stats or history API")
            return PlayerStats(self._client, self.uid).win_rate(season=season, mode=mode or "all")
        if method not in ("estimate", "exact", "cached"):
            raise ValueError("method must be estimate, exact, or cached")
        if method == "estimate":
            if mode == "all" and hero is None and teammate is None:
                return PlayerStats(self._client, self.uid).win_rate(season=season, mode=mode)
            if hero is not None or teammate is not None or mode not in (None, "competitive"):
                raise ValueError("summary estimates support competitive overall only; use method='exact'")
            return self._estimated_overall_win_rate(season=season)
        if method == "cached":
            rows, entry = self._cached_history(season=season, mode=mode, hero=hero,
                                               teammate=teammate, cached=cached)
            result = self._calculate_match_rate(rows)
            result.update({"method": "cached", "sources": entry["sources"],
                           "cache_complete": entry["complete"]})
            return DataModel(result)

        if mode == "all":
            from .stat_scope import scoped_history

            if hero is not None or teammate is not None:
                raise ValueError("Use a single mode for legacy filtered history calculations")
            rows, history_metadata = scoped_history(self, "all" if season is None else season, mode)
        else:
            history = self.fetch(limit="all", season=None if season == "all" else season,
                                 mode=mode, hero=hero, teammate=teammate, cached=cached)
            rows = {str(row.match_uid): row.to_dict() for row in history.matches}
            history_metadata = history.provider_metadata
        result = self._calculate_match_rate(list(rows.values()))
        result.update({"method": "exact", "sources": history_metadata.get("sources", []),
                       "provider_errors": history_metadata.get("errors", []),
                       "scope": {"season": season, "mode": mode, "hero": hero,
                                 "teammate": teammate}})
        return DataModel(result)

    def _estimated_overall_win_rate(self, *, season: int | None = None) -> DataModel:
        client = self._client
        error_start = len(client.provider_errors)
        errors = []
        try:
            profile = self._post("/player")
        except RivalsDataError as exc:
            profile = {}
            errors.append({"source": "rivalsdata", "error": str(exc)})
        ranks = profile.get("rank_game_season", {}) if isinstance(profile, dict) else {}
        rank_rows = [(str(key), value) for key, value in ranks.items()
                     if str(key).startswith("1001") and isinstance(value, dict)]
        target_season = season
        if target_season is None and rank_rows:
            target_season = max(rank_rows, key=lambda item: int(item[1].get("rank_game_id", 0)))[1].get("rank_game_id")
        rd_row = next((row for key, row in rank_rows
                       if str(row.get("rank_game_id", key.removeprefix("1001"))) == str(target_season)), None)
        rates = []
        if rd_row:
            rate = self._rate_from_counts(rd_row.get("battle_count"), rd_row.get("win_count"))
            if rate is not None:
                rates.append({"source": "rivalsdata", "matches": rd_row.get("battle_count"),
                              "wins": rd_row.get("win_count"), "win_rate_pct": rate})
        body = client._rt_player(self.uid, target_season)
        stats = body.get("stats", {}) if isinstance(body, dict) else {}
        rate = self._rate_from_counts(stats.get("ranked_matches"), stats.get("ranked_matches_wins"))
        if rate is not None:
            rates.append({"source": "rivalstracker", "matches": stats.get("ranked_matches"),
                          "wins": stats.get("ranked_matches_wins"), "win_rate_pct": rate})
        errors.extend(client.provider_errors[error_start:])
        values = [row["win_rate_pct"] for row in rates]
        mean = sum(values) / len(values) if values else None
        return DataModel({"win_rate": round(mean) if mean is not None else None,
                          "win_rate_pct": round(mean, 2) if mean is not None else None,
                          "method": "estimate",
                          "estimate_method": "unweighted_mean_of_available_provider_rates",
                          "matches": None, "known_results": None,
                          "provider_rates": rates, "sources": [row["source"] for row in rates],
                          "provider_errors": errors,
                          "scope": {"season": target_season, "mode": "competitive"},
                          "exact": False})

    @staticmethod
    def _rate_from_counts(games: Any, wins: Any) -> float | None:
        if (isinstance(games, (int, float)) and not isinstance(games, bool)
                and isinstance(wins, (int, float)) and not isinstance(wins, bool)
                and games > 0 and 0 <= wins <= games):
            return round(100 * wins / games, 2)
        return None

    @staticmethod
    def _calculate_match_rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        unique = {str(row["match_uid"]): row for row in rows if row.get("match_uid") is not None}
        wins = losses = unknown = 0
        for row in unique.values():
            outcome = row.get("is_win")
            if outcome is True or outcome == 1:
                wins += 1
            elif outcome is False or outcome == 0:
                losses += 1
            else:
                camp, winner = row.get("camp"), row.get("winner_camp")
                if camp is not None and winner is not None and str(camp) == str(winner):
                    wins += 1
                elif camp is not None and winner is not None:
                    losses += 1
                else:
                    unknown += 1
        known = wins + losses
        return {"wins": wins, "losses": losses, "matches": len(unique),
                "known_results": known, "unknown_results": unknown,
                "win_rate": round(wins * 100 / known) if known else None,
                "win_rate_pct": round(wins * 100 / known, 2) if known else None,
                "deduplicated": True,
                "basis": "unique match IDs; wins / (wins + losses) * 100"}

    def _cached_history(self, *, season=None, mode=None, hero=None, teammate=None,
                        cached=True):
        requested = (self.uid, season, mode, str(hero) if hero is not None else None,
                     str(teammate) if teammate is not None else None, cached)
        entry = (self._client._match_history_cache.get((self.uid, None, None, None, None, cached))
                 or self._client._match_history_cache.get((self.uid, season, None, None, None, cached))
                 or self._client._match_history_cache.get(requested))
        if entry is None:
            raise ValueError("No complete match history is cached; call matches.fetch(limit='all') first")
        if teammate is not None:
            raise ValueError("Cached history summaries cannot verify teammate membership")
        rows = self._select_cached_rows(entry["matches"], season=season, mode=mode, hero=hero)
        return rows, entry

    def _select_cached_rows(self, rows, *, season=None, mode=None, hero=None):
        selected = rows
        if season not in (None, "all"):
            selected = [row for row in selected if str(row.get("season")) == str(season)]
        if mode is not None:
            identifiers = {1, 2} if mode == "all" else {mode_id(mode)}
            selected = [row for row in selected if row.get("game_mode_id") in identifiers]
        if hero is not None:
            identifier = int(hero) if str(hero).isdecimal() else hero_id(str(hero))
            selected = [row for row in selected if str(row.get("hero_id")) == str(identifier)]
        return selected

    def fetch_hero_win_rates(
        self, *, method: Literal["estimate", "exact", "cached"] | None = None,
        season: int | Literal["all"] | None = None,
        mode: Literal["competitive", "quickplay", "all"] = "all",
    ) -> DataModel:
        """Canonical match attribution by default; method is a legacy override."""
        if method is None or method == "exact":
            return PlayerStats(self._client, self.uid).hero_win_rates(season=season, mode=mode)
        if method == "estimate":
            if mode == "all":
                return PlayerStats(self._client, self.uid).hero_win_rates(season=season, mode=mode)
            return self._estimated_character_rates(mode=mode, season=season, group="hero")
        rows, sources, errors = self._history_for_character_rates(
            method=method, season=season, mode=mode)
        stats = self._character_match_rates(rows, group="hero", exact=method == "exact")
        return DataModel({**stats, "method": method, "sources": sources,
                          "provider_errors": errors, "scope": {"season": season, "mode": mode}})

    def fetch_class_win_rates(
        self, *, method: Literal["estimate", "exact", "cached"] | None = None,
        season: int | Literal["all"] | None = None,
        mode: Literal["competitive", "quickplay", "all"] = "all",
    ) -> DataModel:
        """Canonical match attribution by default; method is a legacy override."""
        if method is None or method == "exact":
            return PlayerStats(self._client, self.uid).class_win_rates(season=season, mode=mode)
        if method == "estimate":
            if mode == "all":
                return PlayerStats(self._client, self.uid).class_win_rates(season=season, mode=mode)
            return self._estimated_character_rates(mode=mode, season=season, group="class")
        rows, sources, errors = self._history_for_character_rates(
            method=method, season=season, mode=mode)
        stats = self._character_match_rates(rows, group="class", exact=method == "exact")
        return DataModel({**stats, "method": method, "sources": sources,
                          "provider_errors": errors, "scope": {"season": season, "mode": mode}})

    def _history_for_character_rates(self, *, method, season, mode):
        if method == "exact":
            history = self.fetch(limit="all", season=season, mode=mode)
            return ([row.to_dict() for row in history.matches],
                    history.provider_metadata.get("sources", []),
                    history.provider_metadata.get("errors", []))
        if method != "cached":
            raise ValueError("method must be estimate, exact, or cached")
        rows, entry = self._cached_history(season=season, mode=mode)
        return rows, entry["sources"], []

    def _estimated_character_rates(self, *, mode, season, group):
        if mode not in ("competitive", "quickplay"):
            raise ValueError("mode must be competitive or quickplay")
        client = self._client
        error_start = len(client.provider_errors)
        errors = []
        season_id = -1 if season == "all" else season
        payload = {"season": season_id} if season_id is not None else {}
        sources: dict[str, dict[str, dict[str, float]]] = {}
        try:
            rows = self._post("/player/stats/heroes", **payload)
        except RivalsDataError as exc:
            rows = []
            errors.append({"source": "rivalsdata", "error": str(exc)})
        rd: dict[str, dict[str, float]] = {}
        for row in rows:
            hero = row.get("hero_id")
            stat = row.get(mode)
            if hero is None or not isinstance(stat, dict):
                continue
            games, wins = stat.get("games", stat.get("matches")), stat.get("wins")
            if self._rate_from_counts(games, wins) is not None:
                rd[str(hero)] = {"matches": float(games), "wins": float(wins)}
        if rd:
            sources["rivalsdata"] = rd

        body = client._rt_player(self.uid, season_id) if season_id != -1 else None
        rt_key = "heroes_ranked" if mode == "competitive" else "heroes_unranked"
        rt_map = (body or {}).get(rt_key, {})
        rt: dict[str, dict[str, float]] = {}
        for hero, stat in rt_map.items():
            games, wins = stat.get("matches"), stat.get("win")
            if self._rate_from_counts(games, wins) is not None:
                rt[str(hero)] = {"matches": float(games), "wins": float(wins)}
        if rt:
            sources["rivalstracker"] = rt
        errors.extend(client.provider_errors[error_start:])

        if group == "hero":
            grouped: dict[str, dict[str, Any]] = {}
            for source, heroes in sources.items():
                for hero, counts in heroes.items():
                    record = grouped.setdefault(hero, {"hero_id": int(hero), "providers": []})
                    rate = self._rate_from_counts(counts["matches"], counts["wins"])
                    record["providers"].append({"source": source, **counts,
                                                 "win_rate_pct": rate})
            data = []
            for record in grouped.values():
                rates = [row["win_rate_pct"] for row in record["providers"]]
                mean = sum(rates) / len(rates) if rates else None
                data.append({"hero_id": record["hero_id"], "hero_name": hero_name(record["hero_id"]),
                             "player_class": hero_class(record["hero_id"]),
                             "provider_rates": record["providers"],
                             "win_rate": round(mean) if mean is not None else None,
                             "win_rate_pct": round(mean, 2) if mean is not None else None})
            data.sort(key=lambda row: row["hero_id"])
            return DataModel({"data": data, "method": "estimate",
                              "estimate_method": "unweighted_mean_of_available_provider_rates",
                              "sources": sorted(sources), "provider_errors": errors,
                              "scope": {"season": season, "mode": mode},
                              "counts_basis": "provider hero-participation summaries",
                              "exact": False})

        by_source: dict[str, dict[str, dict[str, float]]] = {}
        for source, heroes in sources.items():
            grouped_classes: dict[str, dict[str, float]] = {}
            for hero, counts in heroes.items():
                name = hero_class(int(hero))
                if name is None:
                    continue
                total = grouped_classes.setdefault(name, {"matches": 0.0, "wins": 0.0})
                total["matches"] += counts["matches"]
                total["wins"] += counts["wins"]
            by_source[source] = grouped_classes
        class_names = sorted({name for groups in by_source.values() for name in groups})
        data = []
        for name in class_names:
            provider_rates = []
            for source, groups in by_source.items():
                counts = groups.get(name)
                if counts:
                    provider_rates.append({"source": source, **counts,
                                           "win_rate_pct": self._rate_from_counts(
                                               counts["matches"], counts["wins"])})
            rates = [row["win_rate_pct"] for row in provider_rates]
            mean = sum(rates) / len(rates) if rates else None
            data.append({"player_class": name, "provider_rates": provider_rates,
                         "win_rate": round(mean) if mean is not None else None,
                         "win_rate_pct": round(mean, 2) if mean is not None else None})
        return DataModel({"data": data, "method": "estimate",
                          "estimate_method": "unweighted_mean_of_provider_class_rates",
                          "sources": sorted(sources), "provider_errors": errors,
                          "scope": {"season": season, "mode": mode},
                          "counts_basis": "summed hero participation; one provider-level rate per class",
                          "exact": False})

    def _character_match_rates(self, rows, *, group, exact):
        from .attribution import attribute_match

        aggregated: dict[str, dict[str, Any]] = {}
        errors = []
        unresolved = []
        details_loaded = fallbacks = unknown_result = 0
        for row in rows:
            match_id = row.get("match_uid")
            if match_id is None:
                continue
            detail = self._client._match_detail_cache.get(
                (str(match_id), bool(self._client.enrich)))
            if detail is None and exact:
                error_start = len(self._client.provider_errors)
                try:
                    detail = self._client.matches.get(match_id).to_dict()
                    details_loaded += 1
                except RivalsDataError as exc:
                    errors.append({"match_uid": str(match_id), "error": str(exc)})
                errors.extend(self._client.provider_errors[error_start:])
            assignment, reason = attribute_match(
                detail or {}, self.uid, self._client._player_names.get(self.uid), row)
            if assignment is None:
                unresolved.append({"match_uid": str(match_id), "reason": reason})
                continue
            selected_hero = assignment["hero_id"]
            try:
                identifier = int(selected_hero)
            except (TypeError, ValueError):
                continue
            class_name = hero_class(identifier)
            key = str(identifier) if group == "hero" else class_name
            if key is None:
                continue
            item = aggregated.setdefault(key, {"hero_id": identifier if group == "hero" else None,
                                               "player_class": class_name,
                                               "matches": 0, "wins": 0, "losses": 0,
                                               "unknown_results": 0, "heroes": set()})
            item["matches"] += 1
            item["heroes"].add(identifier)
            outcome = assignment["is_win"]
            if outcome is True or outcome == 1:
                item["wins"] += 1
            elif outcome is False or outcome == 0:
                item["losses"] += 1
            else:
                item["unknown_results"] += 1
                unknown_result += 1
        data = []
        for key, item in aggregated.items():
            known = item["wins"] + item["losses"]
            item["win_rate"] = round(item["wins"] * 100 / known) if known else None
            item["win_rate_pct"] = round(item["wins"] * 100 / known, 2) if known else None
            item["hero_ids"] = sorted(item.pop("heroes"))
            if group == "hero":
                item["hero_name"] = hero_name(item["hero_id"])
            data.append(item)
        data.sort(key=lambda row: (-row["matches"], row.get("hero_id") or 0))
        return {"data": data, "matches_analyzed": len(rows),
                "details_loaded": details_loaded, "summary_hero_fallbacks": fallbacks,
                "unknown_results": unknown_result,
                "unresolved": unresolved,
                "attribution_rule": "unique hero with maximum per-match play_time",
                "provider_errors": errors}

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

    def get(self, match_id: str | int, *, refresh: bool = False) -> Match:
        """Get combined typed details; refresh bypasses client/provider caches."""
        from .match_details import fetch_match

        return fetch_match(self._client, match_id, refresh=refresh)
