"""Shared season/mode boundaries for canonical player statistics."""

MODES = {"competitive": 2, "quickplay": 1}


def validate_mode(mode):
    if mode not in (*MODES, "all"):
        raise ValueError("mode must be competitive, quickplay, or all")
    return tuple(MODES) if mode == "all" else (mode,)


def resolve_season(resource, season):
    if season is None:
        season = resource.analytics.seasons().data.get("currentSeason")
        if not isinstance(season, int) or isinstance(season, bool) or season < 1:
            raise ValueError("Cannot verify the current season; supply a season ID or 'all'")
    if season != "all" and (isinstance(season, bool) or not isinstance(season, int) or season < 1):
        raise ValueError("season must be a positive ID or 'all'")
    return season


def scoped_history(resource, season, mode):
    from .resources import PlayerMatches

    modes = validate_mode(mode)
    history = PlayerMatches(resource._client, resource.uid).fetch(
        limit="all", season=None if season == "all" else season,
        mode=None if mode == "all" else mode)
    allowed = {MODES[item] for item in modes}
    rows = {str(row.match_uid): row.to_dict() for row in history.matches
            if row.get("match_uid") and row.get("game_mode_id") in allowed}
    return rows, history.provider_metadata.to_dict()
