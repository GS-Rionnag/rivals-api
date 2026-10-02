"""History federation with resumable, filter-bound provider cursors."""

from __future__ import annotations

import base64
import json

from .exceptions import RivalsDataError, RivalsDataHTTPError
from .models import MatchHistory
from .normalize import merge, mode_id, rt_history, timestamp

PREFIX = "rivals:v1:"


def fetch_history(resource, *, cursor=None, season=None, mode=None, hero=None,
                  teammate=None, cached=True, limit=None, include_rt=True):
    mode = mode_id(mode)
    scope = {"uid": resource.uid, "season": season, "mode": mode,
             "hero": str(hero) if hero is not None else None,
             "teammate": str(teammate) if teammate is not None else None,
             "cached": cached, "include_rt": include_rt}
    state = {"rd": cursor, "rt": 0, "rd_done": False,
             "rt_done": not include_rt, "seen": [], "pending": []}
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
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Invalid history cursor or changed filters") from exc
    seen = set(state["seen"])
    rows = {str(row["match_uid"]): row for row in state.pop("pending", [])
            if isinstance(row, dict) and row.get("match_uid") is not None}
    errors = []
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
            state["rd"] = primary.get("next_cursor")
            state["rd_done"] = not bool(state["rd"])
        except RivalsDataError as exc:
            errors.append({"source": "rivalsdata", "error": str(exc)})
            # The failing source can be retried by starting a new traversal.
            state["rd_done"] = True
    if include_rt and teammate is not None:
        # RT does not expose this filter, and summary rows cannot verify it.
        state["rt_done"] = True
        errors.append({"source": "rivalstracker", "error": "teammate filter unsupported"})
    if include_rt and (limit is None or len(rows) < limit) and not state["rt_done"] and teammate is None:
        # Skip duplicate-only RT pages so callers don't mistake an empty page
        # for the end of the federated history. Work remains bounded per call.
        for _ in range(10):
            try:
                data = resource._client.providers.rt.request(
                    f"/player-match-history/{resource.uid}", params={"skip": state["rt"],
                        "game_mode_id": mode or 0, "hero_id": hero or 0, "season": season})
                if not isinstance(data, list):
                    raise RivalsDataHTTPError("RivalsTracker returned invalid match history")
                successes += 1
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
                state["rt_done"] = len(data) < 20
                if added or state["rt_done"] or rows:
                    break
            except RivalsDataError as exc:
                errors.append({"source": "rivalstracker", "error": str(exc)})
                state["rt_done"] = True
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
    more = bool(pending) or not (state["rd_done"] and state["rt_done"])
    next_cursor = PREFIX + base64.urlsafe_b64encode(json.dumps(
        {"scope": scope, "state": state}, separators=(",", ":")).encode()).decode() if more else None
    return MatchHistory({**primary, "matches": emitted, "next_cursor": next_cursor,
                         "has_more": more, "source": "combined",
                         "provider_metadata": {"sources": sources, "errors": errors, "scope": scope,
                                               "ordering": "descending_within_page"}}, client=resource._client)
