"""Evidence-based selection, independent of provider popularity or ordering."""

from __future__ import annotations

import math
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

IDENTITY_FIELDS = {"uid", "player_uid", "match_uid", "hero_id", "camp", "team_id", "side"}
COUNT_GROUPS = (("games", "wins", "losses"), ("battle_count", "win_count"))


def update_time(value: Any) -> float | None:
    """Accept real update times, excluding sentinel, future and invalid dates."""
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            result = float(value)
            if result > 1e12:
                result /= 1000
        else:
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            result = date.timestamp()
        if math.isfinite(result) and 978307200 < result <= time.time() + 300:
            return result
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def compatible(left: dict, right: dict) -> bool:
    for key in ("season", "mode", "uid", "match_uid", "hero_id", "counts_basis"):
        if key in left and key in right and str(left[key]) != str(right[key]):
            return False
    return True


def valid(value: Any, field: str) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            return False
        negative_allowed = field.rsplit(".", 1)[-1] in {"score_change", "diff_score", "net_score"}
        return value >= 0 or negative_allowed
    if isinstance(value, dict) and field.endswith("@counts"):
        games = value.get("games", value.get("battle_count"))
        wins = value.get("wins", value.get("win_count"))
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) and v >= 0 for v in (games, wins)):
            return False
        return wins <= games and ("losses" not in value or (
            isinstance(value["losses"], (int, float)) and not isinstance(value["losses"], bool)
            and math.isfinite(value["losses"])
            and math.isclose(value["losses"], games - wins, abs_tol=1e-8)))
    return True


def choose(candidates: list[dict], field: str, current_source: str) -> dict:
    """Return a selected candidate and a human-readable, inspectable decision."""
    current = next((c for c in candidates if c["source"] == current_source), candidates[0])
    scope = current.get("evidence", {}).get("scope", {})
    unit = current.get("evidence", {}).get("unit")
    eligible = [c for c in candidates if valid(c["value"], field)
                and compatible(scope, c.get("evidence", {}).get("scope", {}))
                and (not unit or not c.get("evidence", {}).get("unit")
                     or unit == c["evidence"]["unit"])]
    selected, reason, confidence = current, "insufficient_evidence", "uncertain"
    if eligible:
        selected = current if current in eligible else eligible[0]
        if current not in eligible:
            reason, confidence = "invalid_or_missing_value", "high"
        # Identity mismatches cannot be voted into a different player/match.
        if field.rsplit(".", 1)[-1] in IDENTITY_FIELDS and current in eligible:
            return {"candidate": current, "reason": "identity_preserved", "confidence": "high"}
        # A completed-detail endpoint outranks a history summary. Unknown or
        # absent flags do not imply a completed payload.
        grade = lambda c: (c.get("evidence", {}).get("kind") == "match_detail"
                           and c.get("evidence", {}).get("complete") is True)
        top = max(grade(c) for c in eligible)
        best = [c for c in eligible if grade(c) == top]
        if grade(selected) < top:
            selected, reason, confidence = best[0], "more_complete_record", "high"
        # Do not let one recorded timestamp beat a source with unknown age.
        times = [update_time(c.get("evidence", {}).get("updated_at")) for c in best]
        if len(best) > 1 and all(t is not None for t in times) and max(times) - min(times) >= 5:
            newest = max(times)
            best = [c for c, t in zip(best, times) if t == newest]
            selected, reason, confidence = best[0], "newer_verified_update", "high"
        votes = [[other for other in best if other["value"] == c["value"]] for c in best]
        majority = max(votes, key=len)
        if len(majority) >= 2 and len(majority) > len(best) / 2:
            selected = selected if selected in majority else majority[0]
            reason, confidence = "cross_provider_agreement", "supported"
        elif selected not in best:
            selected = best[0]
        if all(c["value"] == selected["value"] for c in eligible) and len(eligible) > 1:
            reason, confidence = "cross_provider_agreement", "supported"
    else:
        selected = {**current, "value": None}
        reason = "no_valid_comparable_value"
    return {"candidate": selected, "reason": reason, "confidence": confidence}


def resolve(metadata: dict, field: str, primary: Any, incoming: Any,
            source: str, primary_source: str, left_evidence: dict, right_evidence: dict) -> Any:
    """Keep observations so a third source can resolve a two-source tie."""
    observations = metadata.setdefault("observations", {})
    choices = metadata.setdefault("selections", {})
    values = observations.setdefault(field, [])
    if not values:
        values.append({"source": primary_source, "value": deepcopy(primary),
                       "evidence": deepcopy(left_evidence)})
    incoming_candidate = {"source": source, "value": deepcopy(incoming),
                          "evidence": deepcopy(right_evidence)}
    values[:] = [c for c in values if c["source"] != source] + [incoming_candidate]
    current_source = choices.get(field, {}).get("source", primary_source)
    decision = choose(values, field, current_source)
    winner = decision["candidate"]
    choices[field] = {"source": winner["source"], "reason": decision["reason"],
                      "confidence": decision["confidence"], "value": deepcopy(winner["value"])}
    return deepcopy(winner["value"])
