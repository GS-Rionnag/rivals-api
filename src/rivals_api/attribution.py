"""Match-based hero/class records using one longest-played hero per match."""

from __future__ import annotations

import math
import time
from copy import deepcopy

from .exceptions import RivalsDataError
from .hero_ids import hero_class, hero_name
from .normalize import rd_match, rt_match, tracker_match
from .stat_scope import resolve_season, scoped_history, validate_mode


def _rows(value):
    return list(value.values()) if isinstance(value, dict) else list(value or [])


def _player(detail, uid, name):
    players = [p for team in _rows(detail.get("teams"))
               for p in _rows(team.get("players"))]
    matched = [p for p in players
               if str(p.get("player_uid", p.get("uid"))) == str(uid)]
    if len(matched) == 1:
        return matched[0]
    if matched or not name:
        return None
    # Tracker UUIDs are never game UIDs. Exact names must be unique.
    matched = [p for p in players if p.get("name") == name
               and p.get("uid") is None and p.get("player_uid") is None]
    return matched[0] if len(matched) == 1 else None


def _candidate(detail, uid, name):
    player = _player(detail, uid, name)
    if player is None:
        return None, "player_identity_unresolved"
    heroes = _rows(player.get("heroes"))
    times = {}
    for hero in heroes:
        identifier, duration = hero.get("hero_id"), hero.get("play_time")
        if (hero_name(identifier) is None or isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or duration < 0):
            return None, "missing_or_invalid_hero_playtime"
        identifier = int(identifier)
        if identifier in times:
            return None, "duplicate_hero_records"
        times[identifier] = duration
    if not times or max(times.values()) <= 0:
        return None, "missing_or_invalid_hero_playtime"
    longest = max(times.values())
    winners = [identifier for identifier, duration in times.items() if duration == longest]
    if len(winners) != 1:
        return None, "tied_hero_playtime"
    outcome = player.get("is_win")
    if not isinstance(outcome, bool):
        camp, winner = player.get("camp"), detail.get("winner_camp")
        outcome = str(camp) == str(winner) if camp is not None and winner is not None else None
    return {"hero_id": winners[0], "play_time": longest, "is_win": outcome}, None


def attribute_match(detail, uid, name, summary):
    """Compare complete source records; never mix their hero durations."""
    metadata = detail.get("provider_metadata", {})
    responses = metadata.get("responses", {})
    candidates, reasons = [], []
    adapters = {"rivalsdata": rd_match, "rivalstracker": rt_match, "tracker": tracker_match}
    for source, body in responses.items():
        if source not in adapters:
            continue
        normalized = adapters[source](body)
        evidence = normalized.get("provider_metadata", {}).get("evidence", {}).get(source, {})
        if evidence.get("complete") is not True:
            continue
        candidate, reason = _candidate(normalized, uid, name)
        if candidate:
            candidates.append({**candidate, "source": source})
        elif reason == "tied_hero_playtime":
            return None, reason
        else:
            reasons.append(reason)
    if not responses and len(metadata.get("sources", [])) == 1:
        source = metadata["sources"][0]
        if metadata.get("evidence", {}).get(source, {}).get("complete") is True:
            candidate, reason = _candidate(detail, uid, name)
            if candidate:
                candidates.append({**candidate, "source": source})
            else:
                reasons.append(reason)
    if not candidates:
        return None, reasons[0] if reasons else "complete_details_unavailable"
    if len({c["hero_id"] for c in candidates}) != 1:
        return None, "conflicting_longest_hero"
    outcomes = {c["is_win"] for c in candidates if c["is_win"] is not None}
    if len(outcomes) > 1:
        return None, "conflicting_match_outcome"
    if not outcomes:
        outcome = summary.get("is_win")
        if not isinstance(outcome, bool):
            return None, "unknown_match_outcome"
    else:
        outcome = outcomes.pop()
    # Durations remain one provider's record, not a blended total.
    return {**candidates[0], "is_win": outcome,
            "sources": [c["source"] for c in candidates]}, None


def completed_outcome(detail, uid, name):
    """Resolve the outcome independently of hero switches or missing playtime."""
    metadata = detail.get("provider_metadata", {})
    responses = metadata.get("responses", {})
    outcomes = set()
    adapters = {"rivalsdata": rd_match, "rivalstracker": rt_match, "tracker": tracker_match}
    normalized_rows = [(source, adapters[source](body)) for source, body in responses.items()
                       if source in adapters]
    if not responses and len(metadata.get("sources", [])) == 1:
        normalized_rows = [(metadata["sources"][0], detail)]
    for source, normalized in normalized_rows:
        evidence = normalized.get("provider_metadata", {}).get("evidence", {}).get(source, {})
        if evidence.get("complete") is not True:
            continue
        player = _player(normalized, uid, name)
        if player is None:
            continue
        outcome = player.get("is_win")
        if not isinstance(outcome, bool):
            camp, winner = player.get("camp"), normalized.get("winner_camp")
            outcome = str(camp) == str(winner) if camp is not None and winner is not None else None
        if outcome is not None:
            outcomes.add(outcome)
    if len(outcomes) > 1:
        return None, "conflicting_match_outcome"
    return (outcomes.pop(), None) if outcomes else (None, "unknown_match_outcome")


def calculate(resource, *, season=None, mode="all"):
    validate_mode(mode)
    client, uid = resource._client, resource.uid
    season = resolve_season(resource, season)
    key = (uid, season, mode, bool(client.enrich))
    cached = client._attribution_cache.get(key)
    if cached and time.monotonic() - cached[0] < client.provider_cache_ttl:
        return deepcopy(cached[1])
    rows, history_metadata = scoped_history(resource, season, mode)
    heroes, classes, unresolved, assignments = {}, {}, [], []
    errors = list(history_metadata.get("errors", []))
    sources = set(history_metadata.get("sources", []))
    for identifier, summary in rows.items():
        try:
            detail = client._match_detail_cache.get((identifier, bool(client.enrich)))
            assignment, reason = attribute_match(
                detail or {}, uid, client._player_names.get(uid), summary)
            if assignment is None:
                detail = client.matches.get(identifier).to_dict()
                assignment, reason = attribute_match(
                    detail, uid, client._player_names.get(uid), summary)
            errors.extend({"match_uid": identifier, **e} for e in detail.get(
                "provider_metadata", {}).get("errors", []))
        except RivalsDataError as exc:
            assignment, reason = None, "details_unavailable"
            errors.append({"match_uid": identifier, "error": str(exc)})
        if assignment is None:
            unresolved.append({"match_uid": identifier, "reason": reason})
            continue
        assignments.append({"match_uid": identifier, **assignment})
        sources.update(assignment["sources"])
        hero = assignment["hero_id"]
        role = hero_class(hero)
        for groups, group_key in ((heroes, hero), (classes, role)):
            if group_key is None:
                continue
            record = groups.setdefault(group_key, {"games": 0, "wins": 0, "losses": 0,
                                                  "play_time": 0, "hero_ids": set()})
            record["games"] += 1
            record["wins" if assignment["is_win"] else "losses"] += 1
            record["play_time"] += assignment["play_time"]
            record["hero_ids"].add(hero)
    for groups in (heroes, classes):
        for record in groups.values():
            record["win_rate_pct"] = round(record["wins"] * 100 / record["games"], 2)
            record["win_rate"] = round(record["win_rate_pct"])
            record["hero_ids"] = sorted(record["hero_ids"])
    hero_rows = [{**row, "hero_id": hero, "hero_name": hero_name(hero),
                  "player_class": hero_class(hero)} for hero, row in heroes.items()]
    hero_rows.sort(key=lambda row: (-row["games"], row["hero_id"]))
    class_rows = [{**row, "player_class": role,
                   "role": {"tank": "Vanguard", "support": "Strategist", "dps": "Duelist"}[role]}
                  for role, row in classes.items()]
    class_rows.sort(key=lambda row: (-row["games"], row["player_class"]))
    metadata = {"scope": {"uid": uid, "season": season, "mode": mode},
                "attribution_rule": "unique hero with maximum per-match play_time",
                "counts_basis": "deduplicated tracked matches with verified attribution",
                "sources": sorted(sources), "provider_errors": errors,
                "coverage": {"matches_found": len(rows), "matches_attributed": len(assignments),
                             "matches_class_attributed": sum(r["games"] for r in classes.values()),
                             "matches_unresolved": len(unresolved),
                             "all_found_matches_attributed": not unresolved,
                             "complete_game_history_verified": False},
                "unresolved": unresolved, "assignments": assignments}
    result = {"heroes": hero_rows, "classes": class_rows, "metadata": metadata}
    # Retry incomplete evidence on the next query; the transport/detail caches
    # still avoid repeating successful provider requests.
    if not errors and not unresolved:
        client._attribution_cache[key] = time.monotonic(), deepcopy(result)
        while len(client._attribution_cache) > 16:
            client._attribution_cache.pop(next(iter(client._attribution_cache)))
    return result
