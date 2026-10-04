"""New public analytics resources, separate from the legacy response contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from .models import DataModel
from .normalize import tracker_stats


def response(data: Any, source: str, **scope: Any) -> DataModel:
    return DataModel({"data": data, "source": source, "scope": scope})


class PlayerAnalytics:
    def __init__(self, client: Any, uid: int) -> None:
        self.client, self.uid = client, uid

    def rank_history(self, *, season: int | None = None) -> DataModel:
        return response(self.client.providers.rt.request(
            f"/player/{self.uid}/rank-history", params={"season": season}),
            "rivalstracker", season=season)

    def cosmetics(self) -> DataModel:
        return response(self.client.providers.rt.request(
            f"/player/{self.uid}/identity-cosmetics"), "rivalstracker",
            inventory_type="observed_usage", ownership_verified=False)

    def punishment_history(self) -> DataModel:
        return response(self.client.providers.rt.request(
            f"/player/{self.uid}/punishments"), "rivalstracker")

    def matchups(self, *, season: int | None = None) -> DataModel:
        body = self.client.providers.rt.request(f"/player/{self.uid}",
                                                 params={"season": season})
        return response(body.get("matchups", []), "rivalstracker", season=season,
                        opponents="enemy_heroes")

    def encounters(self, *, season: int | None = None, mode: str = "all",
                   local_offset: int = 0) -> DataModel:
        if not -840 <= local_offset <= 840:
            raise ValueError("local_offset must be timezone offset minutes (-840..840)")
        path = self.client._tracker_path(self.uid) + "/aggregated"
        body = self.client.providers.tracker.request(path, params={
            "filter": "encounters", "mode": mode, "season": season,
            "localOffset": local_offset})
        return response(body, "tracker", season=season, mode=mode,
                        local_offset=local_offset, default_window_days=75 if season is None else None)

    def career(self, *, season: int | str | None = None, mode: str = "all") -> DataModel:
        if mode == "quickplay":
            mode = "quick-match"
        if season in ("all", -1):
            # Never treat an omitted season (provider default) as lifetime.
            catalog = self.seasons().data.get("seasons", [])
            rows = []
            for item in catalog:
                rows.extend({**row, "season": item["id"]}
                            for row in self.career(season=item["id"], mode=mode).data)
            return response(rows, "tracker", season="all", mode=mode,
                            aggregation="separate_season_segments", unique_matches_verified=False)
        params = {"mode": mode}
        if season not in (None, "all", -1):
            params["season"] = season
        segments = self.client.providers.tracker.request(
            self.client._tracker_path(self.uid) + "/segments/career", params=params)
        rows = [{"type": s.get("type"), "attributes": s.get("attributes", {}),
                 "metadata": s.get("metadata", {}), **tracker_stats(s)} for s in segments]
        return response(rows, "tracker", season=season, mode=mode,
                        counts_basis="provider_hero_participation", unique_matches_verified=False)

    def rank_stats(self, *, season: int | None = None) -> DataModel:
        return response(self.client.providers.tracker.request(
            self.client._tracker_path(self.uid) + "/stats/overview/ranked",
            params={"season": season}), "tracker", season=season)

    def seasons(self) -> DataModel:
        body = self.client.providers.tracker.request(self.client._tracker_path(self.uid))
        meta = body.get("metadata") if isinstance(body, Mapping) else None
        meta = meta if isinstance(meta, Mapping) else {}
        values = {k: meta.get(k) for k in ("seasons", "currentSeason", "defaultSeason")}
        fallback = body.get("provider_metadata", {}).get("fallback") if isinstance(body, Mapping) else None
        if fallback:
            values["currentSeason"] = None  # A stale profile cannot prove today's global season.
            values["provider_metadata"] = {"fallback": fallback}
        return response(values,
                        "tracker")


class GameAnalytics:
    def __init__(self, client: Any) -> None:
        self.client = client

    def hero_stats(self, *, season: int | None = None) -> DataModel:
        return response(self.client.providers.rt.request("/heroes/stats", params={"season": season}),
                        "rivalstracker", season=season)

    def hero_matchups(self, hero_id: int | str | None = None) -> DataModel:
        body = self.client.providers.rt.request("/hero-matchups")
        if hero_id is not None:
            body = body.get(str(hero_id), {})
        return response(body, "rivalstracker", platforms="all", ranks="all",
                        season_filter_supported=False)

    def team_compositions(self) -> DataModel:
        return response(self.client.providers.rt.request("/roles/data"), "rivalstracker")

    def rank_distribution(self) -> DataModel:
        rows = self.client.providers.rt.request("/rank-distribution/data")
        total = sum(row.get("total", 0) for row in rows)
        return response({"total": total, "ranks": [
            {**row, "percentage": row.get("total", 0) * 100 / total if total else None}
            for row in rows]}, "rivalstracker", population="provider_tracked_players")

    def skin_popularity(self) -> DataModel:
        return response(self.client.providers.rt.request("/hero-skins"), "rivalstracker",
                        ownership_verified=False)

    def hero_history(self, hero_id: int | str, *, days: int = 30,
                     platform: str = "pc") -> DataModel:
        if days not in (30, 90, 180):
            raise ValueError("days must be 30, 90, or 180")
        if platform not in ("pc", "console"):
            raise ValueError("platform must be pc or console")
        return response(self.client.providers.rt.request(
            f"/hero-stats-history/{quote(str(hero_id), safe='')}",
            params={"days": days, "platform": platform}), "rivalstracker",
            days=days, platform=platform, rank="celestial+")

    def hero_players(self, hero_id: int | str, *, season: int | None = None,
                     device: int = 1) -> DataModel:
        return response(self.client.providers.rt.request(
            f"/hero-players/{quote(str(hero_id), safe='')}",
            params={"season": season, "device": device}), "rivalstracker",
            season=season, device=device)

    def hero_reference(self, hero_id: int | str | None = None) -> DataModel:
        # A dated packaged public catalog supports abilities without a browser.
        import json
        from importlib.resources import files

        catalog = json.loads(files("rivals_api").joinpath("hero_catalog.json").read_text(encoding="utf-8"))
        rows = catalog["heroes"]
        if hero_id is not None:
            rows = [row for row in rows if str(row.get("hero_id")) == str(hero_id)]
        return response(rows, "rivalstracker_static", snapshot_date=catalog["snapshot_date"])


class Community:
    def __init__(self, client: Any) -> None:
        self.client = client

    def crosshairs(self, *, page: int = 1, sort: str = "upvotes", players: str = "all",
                  search: str | None = None, name: str | None = None) -> DataModel:
        if page < 1:
            raise ValueError("page must be positive")
        params = {"platformUserIdentifier": name} if name else {
            "page": page, "sort": sort, "players": players, "search": search}
        rows = self.client.providers.tracker.request("/api/v1/marvel-rivals/crosshairs", params=params)
        return response(rows, "tracker", page=page, page_size=20)

    def looking_for_group(self, **filters: Any) -> DataModel:
        return response(self.client.providers.tracker.request(
            "/api/v1/marvel-rivals/lfg/search", params={
                key: ",".join(value) if isinstance(value, list) else value
                for key, value in filters.items() if value != "all"}), "tracker")
