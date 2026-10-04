"""Resilient, source-aware full match fetching for history rows and ID lookups."""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .exceptions import RivalsDataError, RivalsDataHTTPError
from .models import Match
from .normalize import merge_match, rd_match, rt_match, tracker_match


def _json_safe(value: Any) -> Any:
    """Preserve unusable raw numbers as text without emitting invalid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def fetch_match(client: Any, match_id: str | int, *, refresh: bool = False) -> Match:
    """Combine matching details; keep outages, raw responses and conflicts visible."""
    if match_id is None or isinstance(match_id, bool) or not str(match_id).strip():
        raise ValueError("match_id must be a nonempty match identifier")
    identifier = str(match_id)
    enrich = bool(getattr(client, "enrich", False))
    cached = client._cached_match_detail(identifier)
    cached_metadata = cached.get("provider_metadata", {}) if cached else {}
    if (cached is not None and not refresh and not cached_metadata.get("errors")
            and not cached_metadata.get("unmatched_players")
            and all(c.get("complete") is True for c in cached_metadata.get("evidence", {}).values())):
        return Match(deepcopy(cached), client=client)

    encoded = quote(identifier, safe="")
    sources = [("rivalsdata", "/match", rd_match)]
    if enrich:
        sources += [("rivalstracker", "/matches/" + encoded, rt_match),
                    ("tracker", "/api/v2/marvel-rivals/standard/matches/" + encoded, tracker_match)]
    result: dict = {}
    errors: list[dict] = []
    responses: dict = {}
    for source, path, normalize in sources:
        try:
            if source == "rivalsdata":
                body = client._post_json(path, {"match_id": identifier})
            else:
                transport = client.providers.rt if source == "rivalstracker" else client.providers.tracker
                body = transport.request(path, **({"refresh": True} if refresh else {}))
            if not isinstance(body, dict):
                raise RivalsDataHTTPError(f"{source} returned invalid match details")
            attributes = body.get("attributes")
            returned_id = (attributes.get("id") if isinstance(attributes, dict) else None) if source == "tracker" else body.get("match_uid")
            if returned_id is None or str(returned_id) != identifier:
                raise RivalsDataHTTPError(f"{source} returned a missing or different match ID")
            try:
                normalized = normalize(body)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise RivalsDataHTTPError(f"{source} returned malformed match details: {exc}") from exc
            responses[source] = _json_safe(deepcopy(body))
            result = merge_match(result, normalized, source) if result else normalized
        except RivalsDataError as exc:
            if not enrich:
                raise
            error = {"source": source, "path": path, "error": str(exc)}
            errors.append(error)
            client.provider_errors.append(deepcopy(error))
            client.provider_errors[:] = client.provider_errors[-100:]

    if not result.get("match_uid"):
        raise RivalsDataHTTPError("No provider returned this match: " + str(errors))
    metadata = result.setdefault("provider_metadata", {})
    metadata.setdefault("errors", []).extend(errors)
    metadata["responses"] = responses
    metadata["fetched_at"] = datetime.now(timezone.utc).isoformat()
    evidence = metadata.get("evidence", {})
    teams = result.get("teams", [])
    teams = list(teams.values()) if isinstance(teams, dict) else teams
    metadata["completeness"] = {
        "has_player_details": any(t.get("players") for t in teams),
        "all_requested_providers_succeeded": not errors,
        "providers": {name: context.get("complete") for name, context in evidence.items()},
        "unmatched_player_count": len(metadata.get("unmatched_players", [])),
    }
    # Retain partial evidence for request-free calculations, while the cache
    # read above retries it for get_details() instead of freezing an outage.
    client._store_match_detail(identifier, deepcopy(result))
    while len(client._match_detail_cache) > 500:
        client._match_detail_cache.pop(next(iter(client._match_detail_cache)))
    return Match(result, client=client)
