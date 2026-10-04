"""Scoped, intact provider summaries. This module never fetches match history."""

from __future__ import annotations

import math
import time
from copy import deepcopy

from .exceptions import RivalsDataError, RivalsDataHTTPError
from .hero_ids import hero_class, hero_name
from .selection import update_time
from .stat_scope import resolve_season, validate_mode

ROLES = {"tank": "Vanguard", "dps": "Duelist", "support": "Strategist"}
TRACKER_ROLES = {"vanguard": "tank", "duelist": "dps", "strategist": "support"}


def mapping(value):
    return value if isinstance(value, dict) else {}


def counts(games, wins):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           or v < 0 for v in (games, wins)) or wins > games + 1e-8:
        return None
    wins = min(wins, games)
    return {"games": games, "wins": wins, "losses": games - wins}


def rates(row):
    value = row["wins"] * 100 / row["games"] if row["games"] else None
    return {**row, "win_rate_pct": round(value, 2) if value is not None else None,
            "win_rate": round(value) if value is not None else None}


def _fingerprint(row):
    if "rows" in row:
        return tuple(sorted((str(r.get("hero_id", r.get("player_class"))), r["games"], r["wins"])
                            for r in row["rows"]))
    return row["games"], row["wins"]


def _select(candidates):
    """Prefer available intact records, comparable agreement, then verified age."""
    if not candidates:
        return None, {"reason": "summary_unavailable", "uncertain": True, "observations": []}
    pool = [r for r in candidates if not r.get("private_snapshot")] or candidates
    # Direct overview counts outrank derived/fallback counts when accessible.
    best_grade = min(r.get("grade", 0) for r in pool)
    pool = [r for r in pool if r.get("grade", 0) == best_grade]
    reason = "single_available_summary" if len(pool) == 1 else "source_priority_unresolved"
    groups = {}
    for row in pool:
        groups.setdefault((row["counts_basis"], _fingerprint(row)), []).append(row)
    agreement = max(groups.values(), key=len)
    if len(agreement) > len(pool) / 2 and len(agreement) > 1:
        pool, reason = agreement, "comparable_provider_agreement"
    else:
        times = [update_time(r.get("updated_at")) for r in pool]
        if len(pool) > 1 and all(t is not None for t in times) and max(times) - min(times) >= 5:
            pool = [r for r, t in zip(pool, times) if t == max(times)]
            reason = "newer_verified_update"
    selected = pool[0]
    disagreement = any(_fingerprint(r) != _fingerprint(selected) for r in candidates)
    return selected, {"reason": reason,
                      "uncertain": disagreement or bool(selected.get("private_snapshot"))
                          or bool(selected.get("missing_seasons")) or best_grade >= 2,
                      "observations": deepcopy(candidates)}


def calculate(resource, *, season=None, mode="all"):
    modes = validate_mode(mode)
    season = resolve_season(resource, season)
    client, uid = resource._client, resource.uid
    key = (uid, season, mode, bool(client.enrich))
    cached = client._summary_rate_cache.get(key)
    if cached:
        ttl = min(client.provider_cache_ttl, 5) if cached[1]["metadata"]["provider_errors"] else client.provider_cache_ttl
        if time.monotonic() - cached[0] < ttl:
            return deepcopy(cached[1])
    errors, excluded = [], []
    candidates = {m: {"overall": [], "heroes": [], "classes": []} for m in modes}

    def request(source, fn):
        try:
            return fn()
        except (RivalsDataError, ValueError, TypeError, AttributeError) as exc:
            errors.append({"source": source, "error": str(exc)})
            return None

    def observation(source, basis, *, private=False, updated=None, grade=0, **values):
        return {"source": source, "counts_basis": basis, "private_snapshot": private,
                "updated_at": updated, "grade": grade, **values}

    def hero_rows(rows, source):
        result, identifiers = [], set()
        for identifier, data in rows:
            if not isinstance(data, dict):
                continue
            if isinstance(identifier, bool) or not str(identifier).isdecimal():
                excluded.append({"source": source, "hero_id": identifier, "reason": "invalid_hero_id"})
                continue
            identifier = int(identifier)
            record = counts(data.get("games"), data.get("wins"))
            if record is None or identifier in identifiers:
                excluded.append({"source": source, "hero_id": identifier, "reason": "invalid_or_duplicate_counts"})
                return None  # Do not select a dataset silently missing invalid rows.
            identifiers.add(identifier)
            result.append({**record, "hero_id": identifier, "hero_name": hero_name(identifier),
                           "player_class": hero_class(identifier),
                           "play_time": data.get("play_time")})
        return result

    selector = -1 if season == "all" else season
    rd = request("rivalsdata", lambda: resource._post("/player/stats/heroes", season=selector))
    if isinstance(rd, list):
        for item in modes:
            rows = hero_rows([(r.get("hero_id"), r.get(item)) for r in rd if isinstance(r, dict)], "rivalsdata")
            if rows:
                candidates[item]["heroes"].append(observation("rivalsdata", "provider_hero_summary", rows=rows))
    elif rd is not None:
        errors.append({"source": "rivalsdata", "error": "Invalid hero summary"})
    maps = request("rivalsdata", lambda: resource._post("/player/stats/maps", season=selector))
    if isinstance(maps, list):
        for item in modes:
            values = [counts(r[item].get("games"), r[item].get("wins")) for r in maps
                      if isinstance(r, dict) and isinstance(r.get(item), dict)]
            if values and all(v is not None for v in values):
                total = {k: sum(v[k] for v in values) for k in ("games", "wins", "losses")}
                candidates[item]["overall"].append(observation("rivalsdata", "map_summary_matches", grade=1, **total))
    profile = request("rivalsdata", lambda: resource._post("/player")) if "competitive" in modes and season != "all" else None
    rank_observations = []
    if isinstance(profile, dict) and str(profile.get("uid")) == str(uid):
        ranks = profile.get("rank_game_season") or {}
        for row in ranks.values() if isinstance(ranks, dict) else []:
            if isinstance(row, dict) and str(row.get("rank_game_id")) == str(season):
                record = counts(row.get("battle_count"), row.get("win_count"))
                if record:
                    fallback = observation("rivalsdata", "rank_system_battles", grade=2,
                                           updated=row.get("update_time"), **record)
                    rank_observations.append(fallback)
                    candidates["competitive"]["overall"].append(fallback)
    if client.enrich:
        if season != "all":
            rt = request("rivalstracker", lambda: client.providers.rt.request(f"/player/{uid}", params={"season": season}))
            if isinstance(rt, dict) and str(mapping(rt.get("player")).get("_id")) == str(uid):
                private = mapping(rt.get("visibility")).get("career_stats") is False
                for item in modes:
                    prefix, hero_key = ("ranked", "heroes_ranked") if item == "competitive" else ("unranked", "heroes_unranked")
                    stats = mapping(rt.get("stats"))
                    record = counts(stats.get(prefix + "_matches"), stats.get(prefix + "_matches_wins"))
                    if record:
                        candidates[item]["overall"].insert(0, observation("rivalstracker", "career_matches", private=private, **record))
                    heroes = rt.get(hero_key)
                    if isinstance(heroes, dict):
                        rows = hero_rows([(h, {**d, "games": d.get("matches"), "wins": d.get("win")})
                                          for h, d in heroes.items() if isinstance(d, dict)], "rivalstracker")
                        if rows:
                            candidates[item]["heroes"].append(observation("rivalstracker", "provider_hero_summary", private=private, rows=rows))
            elif rt is not None:
                errors.append({"source": "rivalstracker", "error": "Missing or different player identity"})
        path = request("tracker", lambda: client._tracker_path(uid))
        tracker_profile = request("tracker", lambda: client.providers.tracker.request(path)) if path else None
        meta = mapping(mapping(tracker_profile).get("metadata"))
        private = meta.get("isPrivateCareerStatistics") is True
        seasons = [season]
        if season == "all":
            catalog = meta.get("seasons")
            catalog = catalog if isinstance(catalog, list) else []
            seasons = [int(r["id"]) for r in catalog if isinstance(r, dict)
                       and str(r.get("id", "")).isdecimal() and int(r["id"]) > 0]
            seasons = sorted(set(seasons))
            if not seasons:
                errors.append({"source": "tracker", "error": "No verified season catalog for lifetime summaries"})
        for item in modes:
            slug = "quick-match" if item == "quickplay" else item
            all_segments, failed_seasons = [], []
            for selected_season in seasons if path else []:
                data = request("tracker", lambda selected_season=selected_season, slug=slug: client.providers.tracker.request(
                    path + "/segments/career", params={"mode": slug, "season": selected_season}))
                if not isinstance(data, list):
                    failed_seasons.append(selected_season)
                    continue
                matching = [s for s in data if isinstance(s, dict) and mapping(s.get("attributes")).get("mode") == slug
                            and str(mapping(s.get("attributes")).get("season")) == str(selected_season)]
                if data and not matching:
                    errors.append({"source": "tracker", "mode": item, "season": selected_season,
                                   "error": "Career segments do not match the requested scope"})
                all_segments.extend(matching)
            totals, heroes, roles = [], {}, {}
            invalid = set()
            seen_segments = set()
            for segment in all_segments:
                attributes, stats = mapping(segment.get("attributes")), mapping(segment.get("stats"))
                record = counts(mapping(stats.get("matchesPlayed")).get("value"), mapping(stats.get("matchesWon")).get("value"))
                kind = segment.get("type")
                if kind not in ("overview", "hero", "hero-role"):
                    continue
                segment_key = (kind, attributes.get("season"), attributes.get("heroId") if kind == "hero" else attributes.get("roleId"))
                if segment_key in seen_segments:
                    invalid.add(kind)
                    errors.append({"source": "tracker", "mode": item, "error": "Duplicate career segment"})
                    continue
                seen_segments.add(segment_key)
                if record is None:
                    invalid.add(kind)
                    excluded.append({"source": "tracker", "type": kind, "reason": "invalid_counts"})
                    continue
                if kind == "overview":
                    totals.append(record)
                    continue
                identifier = attributes.get("heroId") if kind == "hero" else TRACKER_ROLES.get(attributes.get("roleId"))
                if identifier is None:
                    invalid.add(kind)
                    continue
                group = heroes if kind == "hero" else roles
                row = group.setdefault(str(identifier), {"games": 0, "wins": 0, "losses": 0, "play_time": 0})
                for k in record:
                    row[k] += record[k]
                play_time = mapping(stats.get("timePlayed")).get("value")
                if isinstance(play_time, (int, float)) and not isinstance(play_time, bool) and math.isfinite(play_time) and play_time >= 0:
                    row["play_time"] += play_time
            context = {"private": private, "updated": mapping(meta.get("lastUpdated")).get("value"),
                       "missing_seasons": failed_seasons}
            if totals and "overview" not in invalid:
                total = {k: sum(v[k] for v in totals) for k in ("games", "wins", "losses")}
                overall_context = {**context, "private": meta.get("isPrivateCareerOverview") is True}
                candidates[item]["overall"].append(observation("tracker", "career_matches", **overall_context, **total))
            if heroes and "hero" not in invalid:
                rows = hero_rows(heroes.items(), "tracker")
                if rows:
                    candidates[item]["heroes"].append(observation("tracker", "fractional_hero_participation", rows=rows, **context))
            if roles and "hero-role" not in invalid:
                rows = [{**r, "player_class": role, "role": ROLES[role]} for role, r in roles.items()]
                candidates[item]["classes"].append(observation("tracker", "fractional_role_participation", rows=rows, **context))

    by_mode, selected_sources = {}, set()
    hero_groups, class_groups, selections = {}, {}, {}
    for item in modes:
        overall, overall_selection = _select(candidates[item]["overall"])
        selected, hero_selection = _select(candidates[item]["heroes"])
        selections[item] = {"overall": overall_selection, "heroes": hero_selection}
        by_mode[item] = rates(overall) if overall else None
        if overall:
            selected_sources.add(overall["source"])
        if selected:
            selected_sources.add(selected["source"])
            derived = {}
            for row in selected["rows"]:
                identifier = row["hero_id"]
                target = hero_groups.setdefault(identifier, {"hero_id": identifier, "hero_name": row["hero_name"],
                    "player_class": row["player_class"], "games": 0, "wins": 0, "losses": 0, "play_time": None, "by_mode": {}})
                target["by_mode"][item] = {**rates(row), "source": selected["source"], "counts_basis": selected["counts_basis"]}
                for field in ("games", "wins", "losses"):
                    target[field] += row[field]
                if isinstance(row.get("play_time"), (int, float)):
                    target["play_time"] = (target["play_time"] or 0) + row["play_time"]
                role = row["player_class"]
                if role is None:
                    excluded.append({"hero_id": identifier, "reason": "unknown_class"})
                    continue
                group = derived.setdefault(role, {"player_class": role, "role": ROLES[role],
                    "games": 0, "wins": 0, "losses": 0, "hero_ids": [], "play_time": None})
                for field in ("games", "wins", "losses"):
                    group[field] += row[field]
                group["hero_ids"].append(identifier)
                if isinstance(row.get("play_time"), (int, float)):
                    group["play_time"] = (group["play_time"] or 0) + row["play_time"]
            # Keep class results on the selected hero population. Tracker can
            # supply direct role counts instead when it supplies that population.
            direct = next((r for r in candidates[item]["classes"] if r["source"] == selected["source"]), None)
            class_rows = direct["rows"] if direct else list(derived.values())
            basis = direct["counts_basis"] if direct else "summed_" + selected["counts_basis"]
            for row in class_rows:
                role = row["player_class"]
                target = class_groups.setdefault(role, {"player_class": role, "role": ROLES[role],
                    "games": 0, "wins": 0, "losses": 0, "play_time": None, "hero_ids": [], "by_mode": {}})
                target["by_mode"][item] = {**rates(row), "source": selected["source"], "counts_basis": basis}
                target["hero_ids"] = sorted(set(target["hero_ids"]) | set(derived.get(role, {}).get("hero_ids", [])))
                for field in ("games", "wins", "losses"):
                    target[field] += row.get(field, 0)
                if isinstance(row.get("play_time"), (int, float)):
                    target["play_time"] = (target["play_time"] or 0) + row["play_time"]
        else:
            # Direct role summaries remain useful if hero summaries are absent.
            direct, selection = _select(candidates[item]["classes"])
            selections[item]["classes"] = selection
            if direct:
                selected_sources.add(direct["source"])
                for row in direct["rows"]:
                    role = row["player_class"]
                    target = class_groups.setdefault(role, {"player_class": role, "role": ROLES[role],
                        "games": 0, "wins": 0, "losses": 0, "play_time": None, "hero_ids": [], "by_mode": {}})
                    target["by_mode"][item] = {**rates(row), "source": direct["source"], "counts_basis": direct["counts_basis"]}
                    for field in ("games", "wins", "losses"):
                        target[field] += row.get(field, 0)
                    if isinstance(row.get("play_time"), (int, float)):
                        target["play_time"] = (target["play_time"] or 0) + row["play_time"]
    missing_modes = [m for m, r in by_mode.items() if r is None]
    total = {k: sum(r[k] for r in by_mode.values() if r is not None) for k in ("games", "wins", "losses")}
    overall = {**rates(total), "matches": total["games"]} if not missing_modes else {
        "games": None, "matches": None, "wins": None, "losses": None, "win_rate": None, "win_rate_pct": None}
    metadata = {"method": "normal", "scope": {"uid": uid, "season": season, "mode": mode},
                "counts_basis": "selected provider summaries; hero/class participation may differ from unique matches",
                "sources": sorted(selected_sources), "included_modes": list(modes), "by_mode": by_mode,
                "selections": selections, "provider_errors": errors, "excluded": excluded,
                "rank_records": rank_observations,
                "selection_uncertain": bool(missing_modes) or any(v["uncertain"] for s in selections.values() for v in s.values()),
                "coverage": {"history_requested": False, "complete_game_history_verified": False,
                             "missing_overall_modes": missing_modes,
                             "missing_hero_modes": [m for m in modes if not candidates[m]["heroes"]],
                             "missing_class_modes": [m for m in modes if not candidates[m]["heroes"] and not candidates[m]["classes"]]}, "unresolved": []}
    result = {"overall": overall, "heroes": sorted([rates(r) for r in hero_groups.values()], key=lambda r: (-r["games"], r["hero_id"])),
              "classes": sorted([rates(r) for r in class_groups.values()], key=lambda r: (-r["games"], r["player_class"])),
              "metadata": metadata}
    if not any(candidates[m][kind] for m in modes for kind in candidates[m]):
        raise RivalsDataHTTPError("No provider returned usable scoped summaries: " + str(errors))
    client._summary_rate_cache[key] = time.monotonic(), deepcopy(result)
    while len(client._summary_rate_cache) > 32:
        client._summary_rate_cache.pop(next(iter(client._summary_rate_cache)))
    return result
