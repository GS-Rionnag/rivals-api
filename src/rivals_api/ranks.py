"""Verified-name Tracker rank summaries without match-history requests."""

import math


def mapping(value):
    return value if isinstance(value, dict) else {}


def tracker_ranks(body, name):
    if not isinstance(body, dict):
        return None
    platform = mapping(body.get("platformInfo"))
    handle = platform.get("platformUserIdentifier") or platform.get("platformUserHandle")
    if not isinstance(handle, str) or " ".join(handle.casefold().split()) != " ".join(name.casefold().split()):
        return None
    metadata = mapping(body.get("metadata"))
    current_season = metadata.get("currentSeason")
    current, peak = None, None

    def value(raw, season):
        if not isinstance(raw, dict):
            return None
        score = raw.get("value")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0:
            return None
        meta = mapping(raw.get("metadata"))
        return {"rank_score": score, "tier_name": meta.get("tierName"),
                "icon_url": meta.get("iconUrl"), "season": season,
                "source": "tracker", "private_snapshot": metadata.get("isPrivateCareerOverview") is True}

    segments = body.get("segments")
    for segment in segments if isinstance(segments, list) else []:
        if not isinstance(segment, dict):
            continue
        attributes, stats = mapping(segment.get("attributes")), mapping(segment.get("stats"))
        if (segment.get("type") == "overview" and str(current_season).isdecimal()
                and int(current_season) > 0 and str(attributes.get("season")) == str(current_season)
                and attributes.get("mode") in ("all", "competitive")):
            current = value(stats.get("ranked"), current_season)
        if segment.get("type") == "ranked-peaks":
            raw = stats.get("lifetimePeakRanked")
            peak = value(raw, mapping(raw.get("metadata")).get("season")) if isinstance(raw, dict) else None
    if not current and not peak:
        return None
    return {"current": current, "peak": peak, "peak_scope": "lifetime",
            "private_profile": metadata.get("isPrivateCareerOverview") is True
                or metadata.get("isPrivateCareerStatistics") is True,
            "provider_metadata": body.get("provider_metadata", {})}
