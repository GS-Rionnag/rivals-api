"""Exact-scope last-known public responses for transient provider outages."""

import math
import time
from copy import deepcopy

from .exceptions import PrivacyError, RivalsDataError


def request(client, source, key, fetch):
    cache_key = [source, *key]
    try:
        result = fetch()
    except PrivacyError:
        # An explicit access restriction is not a transient outage.
        raise
    except RivalsDataError as exc:
        saved = client._history_store.get("responses-v1", cache_key)
        if not isinstance(saved, dict) or "data" not in saved:
            raise
        saved_at = saved.get("saved_at")
        if isinstance(saved_at, bool) or not isinstance(saved_at, (int, float)) or not math.isfinite(saved_at):
            raise
        if not 0 <= time.time() - saved_at <= client.stale_cache_ttl:
            raise
        # Live status, history frontiers, and current-season discovery must not
        # silently become stale snapshots.
        path = str(key[0])
        if any(word in path for word in ("/matches", "match-history", "/status", "/match", "/live")):
            raise
        fallback = {"source": source, "stale": True, "saved_at": saved["saved_at"],
                    "error": str(exc), "request": key}
        client.provider_errors.append(fallback)
        client.provider_errors[:] = client.provider_errors[-100:]
        value = deepcopy(saved["data"])
        if isinstance(value, dict) and path.startswith("/player"):
            value.pop("status", None)
            if isinstance(value.get("player"), dict):
                value["player"].pop("status", None)

        def mark(row):
            if isinstance(row, dict):
                metadata = row.setdefault("provider_metadata", {})
                if isinstance(metadata, dict):
                    metadata["fallback"] = deepcopy(fallback)

        if isinstance(value, list):
            for row in value:
                mark(row)
        else:
            mark(value)
        return value
    if isinstance(result, (dict, list)) and client.stale_cache_ttl > 0:
        client._history_store.put("responses-v1", cache_key, {"saved_at": time.time(), "data": result})
    return result
