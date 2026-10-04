"""Shared season/mode boundaries for canonical player statistics."""

from .exceptions import RivalsDataError
from .game_ids import numeric_id

MODES = {"competitive": 2, "quickplay": 1}


def validate_method(method):
    if method in (None, "normal", "summary", "estimate"):
        return "normal"
    if method in ("precise", "exact"):
        return "precise"
    raise ValueError("method must be normal or precise (estimate/exact remain aliases)")


def validate_mode(mode):
    if mode not in (*MODES, "all"):
        raise ValueError("mode must be competitive, quickplay, or all")
    return tuple(MODES) if mode == "all" else (mode,)


def resolve_season(resource, season):
    if season is None or season == "current":
        errors = []
        # Current season is global, not the latest season this player played.
        # Do not use defaultSeason, maximum player history, or a static catalog.
        try:
            current = numeric_id(resource.analytics.seasons().data.get("currentSeason"))
            if current is not None and current > 0:
                return current
            errors.append("Tracker currentSeason is missing or invalid")
        except RivalsDataError as exc:
            errors.append(f"Tracker: {exc}")
        try:
            body = resource._client.providers.rt.request("/heroes/stats")
            current = numeric_id(body.get("season")) if isinstance(body, dict) else None
            if current is not None and current > 0:
                return current
            errors.append("RivalsTracker global season is missing or invalid")
        except RivalsDataError as exc:
            errors.append(f"RivalsTracker: {exc}")
        raise ValueError("Cannot verify the current season; supply a positive season ID "
                         "or season='all'. " + "; ".join(errors))
    if season != "all" and (isinstance(season, bool) or not isinstance(season, int) or season < 1):
        raise ValueError("season must be a positive ID, 'current', or 'all'")
    return season


def scoped_history(resource, season, mode):
    from .resources import PlayerMatches

    modes = validate_mode(mode)
    history = PlayerMatches(resource._client, resource.uid).fetch(
        limit="all", season=None if season == "all" else season,
        mode=None if mode == "all" else mode, incremental=True)
    allowed = {MODES[item] for item in modes}
    rows = {str(row.match_uid): row.to_dict() for row in history.matches
            if row.get("match_uid") and row.get("game_mode_id") in allowed}
    return rows, history.provider_metadata.to_dict()
