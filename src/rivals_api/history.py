"""History federation with resumable, filter-bound provider cursors."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote

from .exceptions import RivalsDataError, RivalsDataHTTPError
from .models import MatchHistory
from .normalize import merge, mode_id, rt_history, timestamp, tracker_history

PREFIX = "rivals:v1:"


def fetch_history(resource, *, cursor=None, season=None, mode=None, hero=None,
                  teammate=None, cached=True, limit=None, include_rt=True,
                  stop_at=None, refresh=False):
    mode = mode_id(mode)
    scope = {"uid": resource.uid, "season": season, "mode": mode,
             "hero": str(hero) if hero is not None else None,
             "teammate": str(teammate) if teammate is not None else None,
             "cached": cached, "include_rt": include_rt}
    state = {"rd": cursor, "rt": 0, "rd_done": False,
             "rt_done": not include_rt, "tracker": None,
             "tracker_done": not include_rt, "seen": [], "pending": []}
    if cursor and cursor.startswith(PREFIX):
        try:
            if len(cursor) > 1_000_000:
                raise ValueError("cursor too large")
            decoded = json.loads(base64.urlsafe_b64decode(cursor[len(PREFIX):]))
            if decoded["scope"] != scope:
                raise ValueError("cursor filters do not match the request")
            state = decoded["state"]
            if (not isinstance(state["rt"], int) or state["rt"] < 0
                    or not isinstance(state["seen"], list)
                    or not isinstance(state.get("pending", []), list)):
                raise ValueError("invalid cursor state")
            state.setdefault("pending", [])
            # Old cursors did not traverse Tracker; start that source once.
            state.setdefault("tracker", None)
            state.setdefault("tracker_done", not include_rt)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Invalid history cursor or changed filters") from exc
    seen = set(state["seen"])
    rows = {str(row["match_uid"]): row for row in state.pop("pending", [])
            if isinstance(row, dict) and row.get("match_uid") is not None}
    errors = []
    observed = {}
    progress = state.setdefault("progress", {})

    def checkpoint(source, candidates):
        record = progress.setdefault(source, {"ordered": True, "last": None, "failed": False})
        identifiers = observed.setdefault(source, [])
        overlap = False
        for candidate in candidates:
            identifier = candidate.get("match_uid")
            if not identifier or (season is not None and str(candidate.get("season")) != str(season)):
                continue
            identifiers.append(str(identifier))
            current = timestamp(candidate.get("timestamp"))
            if not current or record["last"] is not None and current > record["last"]:
                record["ordered"] = False
            record["last"] = current
            overlap |= str(identifier) in (stop_at or {}).get(source, set())
        cutoff = overlap and record["ordered"]
        record["cutoff"] = record.get("cutoff", False) or cutoff
        return cutoff

    def failed(source):
        progress.setdefault(source, {"ordered": True, "last": None})["failed"] = True
    primary = {}
    successes = 0
    sources = []
    for row in rows.values():
        sources.extend(source for source in row.get("provider_metadata", {}).get("sources", [])
                       if source not in sources)

    if (limit is None or len(rows) < limit) and not state["rd_done"]:
        payload = {"cursor": state["rd"], **{k: v for k, v in {
            "season": season, "mode": mode, "hero": hero, "teammate": teammate}.items()
            if v is not None}}
        try:
            primary = resource._post("/player/matches/cached" if cached else "/player/matches", **payload)
            if not isinstance(primary, dict) or not isinstance(primary.get("matches"), list):
                raise RivalsDataHTTPError("RivalsData returned invalid match history")
            successes += 1
            sources.append("rivalsdata")
            cutoff = checkpoint("rivalsdata", primary["matches"])
            for row in primary["matches"]:
                identifier = str(row.get("match_uid", ""))
                # The uncached upstream route may ignore selectors. Never
                # leak unfiltered rows into a requested Custom/hero season.
                if (season is not None and str(row.get("season")) != str(season)
                        or mode and str(row.get("game_mode_id")) != str(mode)
                        or hero and str(row.get("hero_id")) != str(hero)):
                    continue
                if teammate is not None and not cached:
                    # Uncached history has no proven teammate selector. Verify
                    # same-team membership from completed detail instead.
                    try:
                        detail = resource._client.matches.get(identifier)
                        teams = detail.get("teams", [])
                        teams = list(teams.values()) if isinstance(teams, dict) else teams
                        shared_team = False
                        for team in teams:
                            players = team.get("players", [])
                            players = list(players.values()) if isinstance(players, dict) else players
                            uids = {str(p.get("player_uid", p.get("uid", ""))) for p in players}
                            if str(resource.uid) in uids and str(teammate) in uids:
                                shared_team = True
                                break
                        if not shared_team:
                            continue
                    except RivalsDataError as exc:
                        errors.append({"source": "rivalsdata", "error": f"Cannot verify teammate for {identifier}: {exc}"})
                        continue
                if identifier and identifier not in seen:
                    rows[identifier] = {**row, "provider_metadata": {"sources": ["rivalsdata"],
                        "evidence": {"rivalsdata": {"kind": "match_summary",
                                                     "scope": {"match_uid": identifier}}}}}
            next_rd = primary.get("next_cursor")
            if next_rd is not None and next_rd == state["rd"] and not cutoff:
                errors.append({"source": "rivalsdata", "error": "Repeated pagination token"})
                failed("rivalsdata")
                next_rd = None
            state["rd"] = next_rd
            state["rd_done"] = cutoff or not bool(state["rd"])
        except RivalsDataError as exc:
            errors.append({"source": "rivalsdata", "error": str(exc)})
            # The failing source can be retried by starting a new traversal.
            state["rd_done"] = True
            failed("rivalsdata")
    if include_rt and teammate is not None:
        # RT does not expose this filter, and summary rows cannot verify it.
        state["rt_done"] = True
        failed("rivalstracker")
        errors.append({"source": "rivalstracker", "error": "teammate filter unsupported"})
    if include_rt and not state["rt_done"] and teammate is None:
        # Skip duplicate-only RT pages so callers don't mistake an empty page
        # for the end of the federated history. Work remains bounded per call.
        for _ in range(10):
            try:
                data = resource._client.providers.rt.request(
                    f"/player-match-history/{resource.uid}", params={"skip": state["rt"],
                        "game_mode_id": mode or 0, "hero_id": hero or 0, "season": season},
                    **({"refresh": True} if refresh else {}))
                if not isinstance(data, list):
                    raise RivalsDataHTTPError("RivalsTracker returned invalid match history")
                successes += 1
                cutoff = checkpoint("rivalstracker", [rt_history(row) for row in data])
                if "rivalstracker" not in sources:
                    sources.append("rivalstracker")
                added = 0
                for row in data:
                    normalized = rt_history(row)
                    identifier = str(normalized.get("match_uid", ""))
                    if (not identifier or identifier in seen
                            or (season is not None and normalized.get("season") != season)
                            or (mode and normalized.get("game_mode_id") != mode)
                            or (hero and str(normalized.get("hero_id")) != str(hero))):
                        continue
                    if identifier in rows:
                        rows[identifier] = merge(rows[identifier], normalized, "rivalstracker")
                    else:
                        rows[identifier] = normalized
                        added += 1
                state["rt"] += 20
                state["rt_done"] = cutoff or len(data) < 20
                if added or state["rt_done"] or rows:
                    break
            except RivalsDataError as exc:
                errors.append({"source": "rivalstracker", "error": str(exc)})
                state["rt_done"] = True
                failed("rivalstracker")
                break
    if include_rt and not state["tracker_done"]:
        name = resource._client._player_names.get(resource.uid)
        if teammate is not None or not name:
            state["tracker_done"] = True
            failed("tracker")
            errors.append({"source": "tracker", "error": "teammate filter unsupported"
                           if teammate is not None else "No verified in-game name for this UID"})
        else:
            # Tracker's season selector can cross seasons; never assign the
            # requested season to a row without independent match evidence.
            for _ in range(10):
                try:
                    data = resource._client.providers.tracker.request(
                        "/api/v2/marvel-rivals/standard/matches/ign/" + quote(name, safe=""),
                        params={"next": state["tracker"], "season": season},
                        **({"refresh": True} if refresh else {}))
                    if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
                        raise RivalsDataHTTPError("Tracker returned invalid match history")
                    successes += 1
                    cutoff = checkpoint("tracker", [tracker_history(row, name) or {} for row in data["matches"]])
                    if "tracker" not in sources:
                        sources.append("tracker")
                    added = 0
                    unknown_season = False
                    for row in data["matches"]:
                        normalized = tracker_history(row, name)
                        if not normalized or not normalized.get("match_uid"):
                            continue
                        identifier = str(normalized["match_uid"])
                        if identifier in seen:
                            continue
                        if normalized.get("season") is None and identifier in rows:
                            normalized["season"] = rows[identifier].get("season")
                        if season is not None and normalized.get("season") is None:
                            unknown_season = True
                            continue
                        if (season is not None and str(normalized.get("season")) != str(season)
                                or mode and normalized.get("game_mode_id") != mode
                                or hero and str(hero) not in {str(h.get("heroId"))
                                                            for h in normalized["heroes"]}):
                            continue
                        if identifier in rows:
                            rows[identifier] = merge(rows[identifier], normalized, "tracker")
                        else:
                            rows[identifier] = normalized
                            added += 1
                    if unknown_season:
                        errors.append({"source": "tracker", "error":
                                       "Skipped matches with unverified season"})
                    next_token = (data.get("metadata") or {}).get("next")
                    state["tracker_done"] = cutoff or next_token is None or next_token == state["tracker"]
                    if next_token is not None and next_token == state["tracker"]:
                        errors.append({"source": "tracker", "error": "Repeated pagination token"})
                        failed("tracker")
                    state["tracker"] = next_token
                    if added or state["tracker_done"] or rows:
                        break
                except RivalsDataError as exc:
                    errors.append({"source": "tracker", "error": str(exc)})
                    state["tracker_done"] = True
                    failed("tracker")
                    break
    if not successes and errors and not seen:
        raise RivalsDataHTTPError("No provider could return match history: " + str(errors))
    result = sorted(rows.values(), key=lambda r: timestamp(r.get("timestamp")), reverse=True)
    if limit is not None and len(result) > limit:
        emitted, pending = result[:limit], result[limit:]
    else:
        emitted, pending = result, []
    state["pending"] = pending
    state["seen"] = sorted(seen | {str(row["match_uid"]) for row in emitted
                                   if row.get("match_uid") is not None})
    more = bool(pending) or not (state["rd_done"] and state["rt_done"] and state["tracker_done"])
    next_cursor = PREFIX + base64.urlsafe_b64encode(json.dumps(
        {"scope": scope, "state": state}, separators=(",", ":")).encode()).decode() if more else None
    checkpoints = {source: {"ids": observed.get(source, []),
                           "complete": state[token + "_done"] and not record.get("failed"),
                           "ordered": record["ordered"], "cutoff": record.get("cutoff", False)}
                   for source, token in (("rivalsdata", "rd"), ("rivalstracker", "rt"), ("tracker", "tracker"))
                   if (record := progress.get(source)) is not None}
    return MatchHistory({**primary, "matches": emitted, "next_cursor": next_cursor,
                         "has_more": more, "source": "combined",
                         "provider_metadata": {"sources": sources, "errors": errors, "scope": scope,
                                               "checkpoints": checkpoints,
                                               "ordering": "descending_within_page"}}, client=resource._client)
