"""Provider adapters. Original values and disagreements remain inspectable."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from .selection import COUNT_GROUPS, resolve

MODE_IDS = {"quickplay": 1, "quick-match": 1, "competitive": 2, "custom": 3}


def mode_id(mode: str | int | None) -> int | None:
    if mode is None:
        return None
    if str(mode).isdecimal():
        return int(mode)
    key = str(mode).casefold()
    if key not in MODE_IDS:
        raise ValueError("mode must be a numeric ID, quickplay, competitive, or custom")
    return MODE_IDS[key]


def merge(primary: dict, extra: dict, source: str, *, context: dict | None = None,
          primary_context: dict | None = None) -> dict:
    """Choose comparable values by evidence, preserving all alternatives."""
    result = deepcopy(primary)
    provenance = result.setdefault("provider_metadata", {})
    provenance.setdefault("sources", [])
    primary_source = provenance["sources"][0] if provenance["sources"] else "rivalsdata"
    if source not in provenance["sources"]:
        provenance["sources"].append(source)
    evidence = provenance.setdefault("evidence", {})
    left_context = {**evidence.get(primary_source, {}), **(primary_context or {})}
    right_context = {**extra.get("provider_metadata", {}).get("evidence", {}).get(source, {}),
                     **(context or {})}
    evidence[primary_source], evidence[source] = left_context, right_context

    def field_context(base: dict, row: dict, key: str) -> dict:
        metadata = {**base}
        if row.get("update_time") is not None:
            metadata["updated_at"] = row["update_time"]
        units = metadata.pop("units", {})
        if key in units:
            metadata["unit"] = units[key]
        return metadata

    def selected_value(field: str, old: Any, new: Any, left: dict, right: dict, key: str) -> Any:
        return resolve(provenance, field, old, new, source, primary_source,
                       field_context(left_context, left, key),
                       field_context(right_context, right, key))

    def fill(left: dict, right: dict, prefix: str = "") -> None:
        original_update = {"update_time": left.get("update_time")}
        grouped = set()
        changed_counts = False
        for group in COUNT_GROUPS:
            if not all(key in right for key in group[:2]):
                continue
            old = {key: left[key] for key in group if key in left}
            new = {key: right[key] for key in group if key in right}
            selected = selected_value(prefix + "@counts", old, new, original_update, right, "@counts")
            if isinstance(selected, dict):
                changed_counts = changed_counts or old != selected
                left.update(selected)
                for key in group:
                    if key in left and key not in selected:
                        left[key] = None
            else:
                left.update({key: None for key in group if key in left})
                changed_counts = True
            grouped.update(group)
        for key, value in right.items():
            if key == "provider_metadata" or key in grouped:
                continue
            field = prefix + key
            if isinstance(left.get(key), dict) and isinstance(value, dict) and key != "tracker_stats":
                fill(left[key], value, field + ".")
            else:
                chosen = selected_value(field, left.get(key), value, original_update, right, key)
                if chosen is not None or key in left:
                    left[key] = chosen
        cohorts = provenance.setdefault("cohort_selections", {})
        if (changed_counts or prefix in cohorts) and "games" in left and "wins" in left:
            games, wins = left["games"], left["wins"]
            for key in ("winrate", "win_rate"):
                if key in left:
                    left[key] = wins * 100 / games if games else None
            # Rates based on the old population must not survive a count change.
            winner = provenance["selections"][prefix + "@counts"]["source"]
            cohorts[prefix] = winner
            rows = provenance.setdefault("records", {})
            selected_row = rows.get(prefix, {}).get(winner, {})
            if games is None or wins is None:
                selected_row = {}
            aliases = {"kills": "kills", "deaths": "deaths", "assists": "assists",
                       "damage": "damage", "healing": "healing", "damage_blocked": "blocked",
                       "finals": "final_hits", "solo_kills": "solo_kills"}
            # Totals and time must describe the same population as its counts.
            # Retaining an old total would make the selected average misleading.
            for key in (*aliases.values(), "play_time", "winning_play_time"):
                if key in left:
                    left[key] = selected_row.get(key)
                    provenance.setdefault("derived_values", {})[prefix + key] = {
                        "value": left[key], "source": winner, "reason": "selected_population_total",
                        "confidence": "supported" if left[key] is not None else "unavailable"}
            play_time = selected_row.get("play_time")
            play_time = play_time if isinstance(play_time, (int, float)) else 0
            for rate, denominator in (("per_game", games), ("per_10", play_time / 600)):
                if rate in left:
                    left[rate] = {key: (selected_row.get(aliases.get(key, key)) / denominator
                                       if denominator and isinstance(selected_row.get(aliases.get(key, key)), (int, float))
                                       else None) for key in left[rate]}
                    for key, value in left[rate].items():
                        provenance.setdefault("derived_values", {})[prefix + rate + "." + key] = {
                            "value": value, "source": winner, "reason": "recomputed_for_selected_population",
                            "confidence": "supported" if value is not None else "unavailable"}
            if "kda" in left:
                deaths = selected_row.get("deaths")
                left["kda"] = ((selected_row["kills"] + selected_row["assists"]) / deaths
                               if deaths and selected_row.get("kills") is not None
                               and selected_row.get("assists") is not None else None)
                provenance.setdefault("derived_values", {})[prefix + "kda"] = {
                    "value": left["kda"], "source": winner, "reason": "recomputed_for_selected_population",
                    "confidence": "supported" if left["kda"] is not None else "unavailable"}

    # Store cohort records for coherent derived values if a later source wins.
    def remember(left: dict, right: dict, prefix: str = "") -> None:
        if any(all(k in right for k in g[:2]) for g in COUNT_GROUPS):
            records = provenance.setdefault("records", {}).setdefault(prefix, {})
            records.setdefault(primary_source, deepcopy({k: v for k, v in left.items() if k != "provider_metadata"}))
            records[source] = deepcopy({k: v for k, v in right.items() if k != "provider_metadata"})
        for key, value in right.items():
            if key != "provider_metadata" and isinstance(value, dict) and isinstance(left.get(key), dict):
                remember(left[key], value, prefix + key + ".")

    remember(primary, extra)
    fill(result, extra)
    conflicts = []
    for field, candidates in provenance.get("observations", {}).items():
        selection = provenance["selections"][field]
        selected = {"source": selection["source"], "value": selection["value"]}
        derived = provenance.get("derived_values", {}).get(field)
        if derived:
            selected = {"value": derived["value"], "source": derived["source"]}
            selection = derived
        for candidate in candidates:
            if candidate["value"] != selected["value"] and candidate["value"] is not None:
                pairs = [(field, selected["value"], candidate["value"])]
                if field.endswith("@counts"):
                    selected_counts = selected["value"] or {}
                    pairs = [(field.removesuffix("@counts") + key, selected_counts.get(key), value)
                             for key, value in candidate["value"].items()
                             if selected_counts.get(key) != value]
                conflicts.extend({"field": name, "selected": deepcopy(chosen),
                                  "selected_source": selected["source"], "source": candidate["source"],
                                  "alternative": deepcopy(alternative),
                                  "reason": selection["reason"], "confidence": selection["confidence"]}
                                 for name, chosen, alternative in pairs)
    provenance["conflicts"] = conflicts
    return result


def rt_profile(body: dict) -> dict:
    player = body.get("player", {})
    info = player.get("info", {})
    ranks = {}
    for key, value in info.items():
        if key.startswith("rank_game_"):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    continue
            if isinstance(value, dict):
                ranks[key.removeprefix("rank_game_")] = value.get("rank_game", value)
    result = {"uid": player.get("_id"), "name": info.get("name"),
              "level": int(info["level"]) if str(info.get("level", "")).isdecimal() else None,
              "icon": info.get("cur_head_icon_id"), "login_os": info.get("login_os"),
              "rank_game_season": ranks, "visibility": body.get("visibility"),
              "provider_updated_at": player.get("info_update_time"),
              "provider_metadata": {"sources": ["rivalstracker"], "evidence": {
                  "rivalstracker": {"kind": "profile", "scope": {"uid": player.get("_id")},
                                     "updated_at": player.get("info_update_time")}}}}
    return {k: v for k, v in result.items() if v is not None}


def rt_history(row: dict) -> dict:
    player = row.get("match_player", {})
    dynamic = player.get("dynamic_fields", {})
    # RivalsTracker may explicitly return score_info=null when a match has no
    # team-score data. Treat that the same as an omitted score object.
    scores = (row.get("dynamic_fields") or {}).get("score_info") or {}
    camp = player.get("camp")
    return {"match_uid": row.get("match_uid"), "game_mode_id": row.get("game_mode_id"),
            "season": int(row["match_season"]) if str(row.get("match_season", "")).isdigit() else None,
            "timestamp": row.get("match_time_stamp"), "map_id": row.get("match_map_id"),
            "duration_seconds": row.get("match_play_duration"),
            "winner_camp": row.get("match_winner_side"),
            "is_win": bool(player["is_win"]) if "is_win" in player else None,
            "kills": player.get("k"), "deaths": player.get("d"), "assists": player.get("a"),
            "hero_id": player.get("player_hero", {}).get("hero_id"),
            "score_change": dynamic.get("add_score"), "rank_score": dynamic.get("new_score"),
            "rank_level": dynamic.get("new_level"),
            "is_mvp": str(row.get("mvp_uid")) == str(player.get("player_uid")) if row.get("mvp_uid") is not None else None,
            "is_svp": str(row.get("svp_uid")) == str(player.get("player_uid")) if row.get("svp_uid") is not None else None,
            "team_score": {"player": scores.get(str(camp)),
                           "opponent": scores.get(str(1 - camp)) if camp in (0, 1) else None},
            "provider_metadata": {"sources": ["rivalstracker"], "evidence": {
                "rivalstracker": {"kind": "match_summary", "scope": {"match_uid": row.get("match_uid")}}}}}


def rt_match(body: dict) -> dict:
    teams: dict[Any, dict] = {}
    for player in body.get("match_players", []):
        camp = player.get("camp")
        heroes = [{"hero_id": h.get("hero_id"), "kills": h.get("k"),
                   "deaths": h.get("d"), "assists": h.get("a"),
                   "play_time": h.get("play_time")} for h in player.get("player_heroes", [])]
        row = {"player_uid": str(player["player_uid"]), "uid": player["player_uid"],
               "name": player.get("nick_name"), "camp": camp,
               "is_win": bool(player["is_win"]) if "is_win" in player else None,
               "kills": player.get("k"), "deaths": player.get("d"), "assists": player.get("a"),
               "damage": player.get("total_hero_damage"), "healing": player.get("total_hero_heal"),
               "damage_taken": player.get("total_damage_taken"),
               "accuracy": player.get("session_hit_rate"), "solo_kills": player.get("solo_kill"),
               "last_kill": player.get("last_kill"), "heroes": heroes,
               "is_mvp": str(body.get("mvp_uid")) == str(player["player_uid"]),
               "is_svp": str(body.get("svp_uid")) == str(player["player_uid"])}
        teams.setdefault(camp, {"camp": camp, "players": []})["players"].append(row)
    return {"match_uid": body.get("match_uid"), "replay_id": body.get("replay_id"),
            "game_mode_id": body.get("game_mode_id"), "timestamp": body.get("match_time_stamp"),
            "duration_seconds": body.get("match_play_duration"), "teams": list(teams.values()),
            "provider_metadata": {"sources": ["rivalstracker"], "evidence": {
                "rivalstracker": {"kind": "match_detail", "complete": bool(body.get("match_players")),
                                     "scope": {"match_uid": body.get("match_uid")}}}}}


def tracker_stats(segment: dict) -> dict:
    """Retain every raw stat under its provider key with display metadata."""
    stats = segment.get("stats", {})
    values = {k: v.get("value") for k, v in stats.items() if isinstance(v, dict)}
    aliases = {"totalHeroDamage": "damage", "totalHeroHeal": "healing",
               "totalDamageTaken": "damage_taken", "headKills": "head_kills",
               "soloKills": "solo_kills", "lastKills": "final_hits",
               "kdRatio": "kd", "kdaRatio": "kda"}
    result = {aliases.get(k, k): v for k, v in values.items()}
    # Damage Taken and the upstream display label "Damage Blocked" differ;
    # never assign this field to the existing blocked semantic.
    for key, normalized in (("timePlayed", "play_time"), ("timePlayedWon", "winning_play_time")):
        value = values.get(key)
        unit = stats.get(key, {}).get("displayType")
        if isinstance(value, (int, float)) and unit in ("TimeMilliseconds", "TimeSeconds"):
            result[normalized] = value / 1000 if unit == "TimeMilliseconds" else value
            if unit == "TimeMilliseconds":
                result[normalized + "_ms"] = value
    result["tracker_stats"] = deepcopy(stats)
    return result


def tracker_match(body: dict) -> dict:
    segments = body.get("segments", [])
    teams: dict[Any, dict] = {}
    for s in segments:
        if s.get("type") != "player":
            continue
        meta, attrs = s.get("metadata", {}), s.get("attributes", {})
        camp = meta.get("teamId")
        row = {**tracker_stats(s), "name": meta.get("platformInfo", {}).get("platformUserIdentifier"),
               "tracker_account_id": attrs.get("accountId"), "camp": camp,
               "is_mvp": meta.get("isMvp"), "is_svp": meta.get("isSvp"),
               "is_win": meta.get("result") == "win", "party_id": meta.get("partyId"),
               "heroes": [{**tracker_stats(h), "hero_id": h.get("attributes", {}).get("heroId")}
                          for h in segments if h.get("type") == "hero"
                          and h.get("attributes", {}).get("accountId") == attrs.get("accountId")]}
        teams.setdefault(camp, {"camp": camp, "players": []})["players"].append(row)
    meta = body.get("metadata", {})
    return {"match_uid": body.get("attributes", {}).get("id"),
            "map_id": body.get("attributes", {}).get("mapId"),
            "duration_seconds": meta.get("duration"), "replay_id": meta.get("replayId"),
            "map_name": meta.get("mapName"), "map_mode_name": meta.get("mapModeName"),
            "full_match_available": meta.get("fullMatchAvailable"),
            "full_match_fetched": meta.get("fullMatchFetched"), "teams": list(teams.values()),
            "provider_metadata": {"sources": ["tracker"], "evidence": {
                "tracker": {"kind": "match_detail",
                             "complete": meta.get("fullMatchAvailable") is True and meta.get("fullMatchFetched") is True,
                             "scope": {"match_uid": body.get("attributes", {}).get("id")}}}}}


def merge_match(primary: dict, extra: dict, source: str) -> dict:
    """Merge team/player/hero rows by identity, not list position or fuzzy names."""
    if (primary.get("match_uid") is not None and extra.get("match_uid") is not None
            and str(primary["match_uid"]) != str(extra["match_uid"])):
        result = deepcopy(primary)
        result.setdefault("provider_metadata", {}).setdefault("errors", []).append(
            {"source": source, "error": "Rejected details for a different match"})
        return result
    result = merge(primary, {k: v for k, v in extra.items() if k != "teams"}, source)
    left_context = primary.get("provider_metadata", {}).get("evidence", {}).get("rivalsdata", {})
    right_context = extra.get("provider_metadata", {}).get("evidence", {}).get(source, {})
    if not result.get("teams"):
        result["teams"] = deepcopy(extra.get("teams", []))
        return result
    teams = result["teams"]
    teams = list(teams.values()) if isinstance(teams, dict) else teams
    candidates = [p for t in extra.get("teams", []) for p in t.get("players", [])]
    for team in teams:
        players = team.get("players", [])
        players = list(players.values()) if isinstance(players, dict) else players
        for index, player in enumerate(players):
            uid = str(player.get("player_uid", player.get("uid", "")))
            name = player.get("name")
            matches = [p for p in candidates if (uid and str(p.get("player_uid", "")) == uid)
                       or (source == "tracker" and name and p.get("name") == name)]
            if len(matches) != 1:
                continue
            candidate = matches[0]
            merged = merge(player, {k: v for k, v in candidate.items() if k != "heroes"}, source,
                           primary_context=left_context, context=right_context)
            heroes = deepcopy(player.get("heroes", []))
            for hero in candidate.get("heroes", []):
                found = next((i for i, h in enumerate(heroes)
                              if str(h.get("hero_id")) == str(hero.get("hero_id"))), None)
                if found is None:
                    heroes.append(deepcopy(hero))
                else:
                    heroes[found] = merge(heroes[found], hero, source,
                                          primary_context=left_context, context=right_context)
            merged["heroes"] = heroes
            players[index] = merged
        team["players"] = players
    result["teams"] = teams
    return result


def timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0
