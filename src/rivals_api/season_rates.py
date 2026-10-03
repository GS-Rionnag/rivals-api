"""Season win rates from intact career records checked against tracked history."""

from __future__ import annotations

import math
import time
from copy import deepcopy

from .exceptions import RivalsDataError
from .selection import update_time
from .stat_scope import MODES, resolve_season, scoped_history, validate_mode


def counts(games, wins):
    values = (games, wins)
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or v < 0 or not float(v).is_integer() for v in values):
        return None
    if wins > games:
        return None
    return {"games": int(games), "wins": int(wins), "losses": int(games - wins)}


def _outcome(resource, row, errors):
    from .attribution import completed_outcome

    client = resource._client
    detail = client._match_detail_cache.get((str(row["match_uid"]), bool(client.enrich)))
    if detail:
        outcome, reason = completed_outcome(detail, resource.uid, client._player_names.get(resource.uid))
        if outcome is not None or reason == "conflicting_match_outcome":
            return outcome
    conflicts = row.get("provider_metadata", {}).get("conflicts", [])
    disputed = any(c.get("field") == "is_win" for c in conflicts)
    if isinstance(row.get("is_win"), bool) and not disputed:
        return row["is_win"]
    try:
        detail = client.matches.get(row["match_uid"]).to_dict()
        return completed_outcome(detail, resource.uid, client._player_names.get(resource.uid))[0]
    except RivalsDataError as exc:
        errors.append({"source": "match_detail", "match_uid": row["match_uid"], "error": str(exc)})
        return None


def _select(records, history):
    """Use agreement/history/freshness, never maximum games or averaged rates."""
    eligible = []
    rejected = []
    for row in records:
        if (row["games"] < history["matches_found"] or row["wins"] < history["wins"]
                or row["losses"] < history["losses"]):
            rejected.append({**row, "reason": "contradicts_tracked_history"})
        else:
            eligible.append(row)
    if not eligible:
        return None, "no_reliable_season_record", rejected, []
    groups = {}
    for row in eligible:
        groups.setdefault((row["games"], row["wins"]), []).append(row)
    # Distinct sources count once; these are provider observations, not proof
    # that the providers obtain their underlying data independently.
    agreement = max(groups.values(), key=len)
    reason = "single_available_season_record"
    pool = eligible
    if len(agreement) > len(eligible) / 2 and len(agreement) > 1:
        pool, reason = agreement, "provider_record_agreement"
    elif history["unknown_results"] == 0 and history["matches_found"]:
        matching = [r for r in eligible if r["games"] == history["matches_found"]
                    and r["wins"] == history["wins"]]
        if matching:
            pool, reason = matching, "matches_tracked_history"
    if len({(r["games"], r["wins"]) for r in pool}) > 1:
        times = [update_time(r.get("updated_at")) for r in pool]
        if all(t is not None for t in times) and max(times) - min(times) >= 5:
            pool = [r for r, t in zip(pool, times) if t == max(times)]
            reason = "newer_verified_update"
        else:
            reason = "unresolved_provider_disagreement"
    selected = pool[0]
    conflicts = [r for r in eligible if (r["games"], r["wins"]) != (
        selected["games"], selected["wins"])]
    return selected, reason, rejected, conflicts


def calculate(resource, *, season=None, mode="all"):
    modes = validate_mode(mode)
    season = resolve_season(resource, season)
    client, uid = resource._client, resource.uid
    key = (uid, season, mode, bool(client.enrich))
    cached = client._season_rate_cache.get(key)
    if cached and time.monotonic() - cached[0] < client.provider_cache_ttl:
        return deepcopy(cached[1])
    errors, observations = [], []
    records = {item: [] for item in modes}
    # RD rank-system battles have not been established as the same population
    # as career matches. Keep the record inspectable without giving it a vote.
    try:
        profile = resource._post("/player") if "competitive" in modes and season != "all" else {}
        if isinstance(profile, dict) and str(profile.get("uid")) == str(uid):
            ranks = profile.get("rank_game_season") or {}
            for value in ranks.values() if isinstance(ranks, dict) else []:
                if isinstance(value, dict) and str(value.get("rank_game_id")) == str(season):
                    record = counts(value.get("battle_count"), value.get("win_count"))
                    if record:
                        observations.append({**record, "source": "rivalsdata", "mode": "competitive",
                            "eligible": False, "reason": "rank_battles_not_verified_as_career_matches"})
    except RivalsDataError as exc:
        errors.append({"source": "rivalsdata", "error": str(exc)})
    if client.enrich and season != "all":
        try:
            body = client.providers.rt.request(f"/player/{uid}", params={"season": season})
            if str((body.get("player") or {}).get("_id")) != str(uid):
                raise ValueError("RivalsTracker returned a different player")
            stats = body.get("stats") or {}
            for item in modes:
                prefix = "ranked" if item == "competitive" else "unranked"
                record = counts(stats.get(prefix + "_matches"), stats.get(prefix + "_matches_wins"))
                if record:
                    records[item].append({**record, "source": "rivalstracker", "mode": item})
        except (RivalsDataError, ValueError, AttributeError) as exc:
            errors.append({"source": "rivalstracker", "error": str(exc)})
        try:
            path = client._tracker_path(uid) + "/segments/career"
        except RivalsDataError as exc:
            path = None
            errors.append({"source": "tracker", "error": str(exc)})
        if path:
            for item in modes:
                slug = "quick-match" if item == "quickplay" else item
                try:
                    segments = client.providers.tracker.request(path, params={"season": season, "mode": slug})
                    candidates = [s for s in segments if s.get("type") == "overview"
                                  and str(s.get("attributes", {}).get("season")) == str(season)
                                  and s.get("attributes", {}).get("mode") == slug]
                    if len(candidates) != 1:
                        raise ValueError("Tracker did not return a unique matching season/mode overview")
                    stats = candidates[0].get("stats") or {}
                    record = counts(stats.get("matchesPlayed", {}).get("value"),
                                    stats.get("matchesWon", {}).get("value"))
                    if record:
                        records[item].append({**record, "source": "tracker", "mode": item})
                except (RivalsDataError, ValueError, TypeError, AttributeError) as exc:
                    errors.append({"source": "tracker", "mode": item, "error": str(exc)})
    try:
        rows, history_metadata = scoped_history(resource, season, mode)
        errors.extend(history_metadata.get("errors", []))
    except RivalsDataError as exc:
        rows = {}
        errors.append({"source": "history", "error": str(exc)})
    histories = {item: {"matches_found": 0, "wins": 0, "losses": 0, "unknown_results": 0}
                 for item in modes}
    for row in rows.values():
        item = next(item for item in modes if MODES[item] == row["game_mode_id"])
        history = histories[item]
        history["matches_found"] += 1
        outcome = _outcome(resource, row, errors)
        history["wins" if outcome is True else "losses" if outcome is False else "unknown_results"] += 1
    results = {}
    for item in modes:
        history = histories[item]
        selected, reason, rejected, conflicts = _select(records[item], history)
        rejected_sources = {r["source"] for r in rejected}
        observations.extend({**r, "eligible": r["source"] not in rejected_sources}
                            for r in records[item])
        if selected is None:
            selected = {"source": "tracked_history", "games": history["wins"] + history["losses"],
                        "wins": history["wins"], "losses": history["losses"]}
        results[item] = {**selected, "selection_reason": reason, "conflicts": conflicts,
                         "rejected_records": rejected, "history": history,
                         "history_matches_record": history["matches_found"] > 0
                             and history["matches_found"] == selected["games"]
                             and history["unknown_results"] == 0 and history["wins"] == selected["wins"],
                         "basis": "tracked_history" if selected["source"] == "tracked_history" else "season_career_record"}
    games = sum(r["games"] for r in results.values())
    wins = sum(r["wins"] for r in results.values())
    losses = sum(r["losses"] for r in results.values())
    rate = wins * 100 / games if games else None
    selected_sources = sorted({r["source"] for r in results.values()})
    result = {"games": games, "matches": games, "wins": wins, "losses": losses,
              "win_rate_pct": round(rate, 2) if rate is not None else None,
              "win_rate": round(rate) if rate is not None else None,
              "metadata": {"scope": {"uid": uid, "season": season, "mode": mode},
                           "sources": selected_sources,
                           "selected_source": selected_sources[0] if len(selected_sources) == 1 else "combined_mode_records",
                           "counts_basis": "season career matches; tracked outcomes for explicit fallbacks",
                           "included_modes": list(modes), "by_mode": results,
                           "provider_records": observations, "provider_errors": errors,
                           "selection_uncertain": any(r["selection_reason"] == "unresolved_provider_disagreement"
                                                      for r in results.values()),
                           "coverage": {"matches_found": len(rows),
                               "unknown_results": sum(r["unknown_results"] for r in histories.values()),
                               "uses_history_fallback": any(r["basis"] == "tracked_history" for r in results.values()),
                               "history_matches_record": all(r["history_matches_record"] for r in results.values()),
                               "complete_game_history_verified": False}}}
    if (not errors and not result["metadata"]["selection_uncertain"]
            and result["metadata"]["coverage"]["unknown_results"] == 0):
        client._season_rate_cache[key] = time.monotonic(), deepcopy(result)
        while len(client._season_rate_cache) > 16:
            client._season_rate_cache.pop(next(iter(client._season_rate_cache)))
    return result
