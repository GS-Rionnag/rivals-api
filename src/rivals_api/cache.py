"""Persistent match evidence; summary and calculation caches remain short lived."""

from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path
from threading import RLock


class MatchCache:
    def __init__(self, directory=None, *, persistent=True):
        root = directory or os.environ.get("RIVALS_API_CACHE_DIR")
        if root is None:
            root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "rivals-api"
        self.path = Path(root) / "matches.sqlite3" if persistent else None
        self.memory = {}
        self.errors = []
        self._connection = None
        self._lock = RLock()

    def _db(self):
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS evidence "
                "(namespace TEXT, key TEXT, body TEXT, PRIMARY KEY(namespace, key))")
        return self._connection

    def _error(self, exc):
        message = str(exc)
        if message not in self.errors:
            self.errors.append(message)

    def get(self, namespace, key):
        encoded = json.dumps(key, separators=(",", ":"))
        with self._lock:
            value = self.memory.get((namespace, encoded))
            if value is None and self.path is not None:
                try:
                    row = self._db().execute(
                        "SELECT body FROM evidence WHERE namespace=? AND key=?",
                        (namespace, encoded)).fetchone()
                    value = json.loads(row[0]) if row else None
                except (OSError, sqlite3.Error, ValueError) as exc:
                    self._error(exc)
            return deepcopy(value)

    def put(self, namespace, key, value):
        encoded = json.dumps(key, separators=(",", ":"))
        with self._lock:
            self.memory[namespace, encoded] = deepcopy(value)
            # Eviction limits RAM only. Historical evidence remains in SQLite.
            if self.path is not None and len(self.memory) > 512:
                self.memory.pop(next(iter(self.memory)))
            if self.path is not None:
                try:
                    body = json.dumps(value, allow_nan=False, separators=(",", ":"))
                    db = self._db()
                    db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?)",
                               (namespace, encoded, body))
                    db.commit()
                except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
                    self._error(exc)

    def close(self):
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


def history_key(client, uid, season):
    return [uid, season, bool(client.enrich)]


def incremental_history(resource, *, season):
    """Refresh each source's newest pages and append its retained history tail."""
    from .history import fetch_history
    from .models import MatchHistory
    from .normalize import timestamp

    client = resource._client
    key = history_key(client, resource.uid, season)
    previous = client._history_store.get("history-v1", key) or {}
    old_rows = {str(r["match_uid"]): r for r in previous.get("matches", [])}
    checkpoints = previous.get("checkpoints", {})
    stop_at = {source: set(item.get("ids", [])) for source, item in checkpoints.items()
               if item.get("complete") and item.get("ordered")}
    rows = dict(old_rows)
    sources, errors, progress = set(previous.get("sources", [])), [], {}
    cursor, seen_cursors = None, set()
    while True:
        from .exceptions import RivalsDataError

        try:
            page = fetch_history(resource, cursor=cursor, season=season, include_rt=bool(client.enrich),
                                 stop_at=stop_at, refresh=True)
        except RivalsDataError as exc:
            if not rows:
                raise
            errors.append({"source": "history", "error": str(exc)})
            break
        for row in page.matches:
            # Updated summaries enrich retained rows; completed details are stored separately.
            value = row.to_dict()
            identifier = str(value["match_uid"])
            if identifier in rows:
                value["provider_metadata"] = {
                    **value.get("provider_metadata", {}),
                    "sources": sorted(set(value.get("provider_metadata", {}).get("sources", []))
                                      | set(rows[identifier].get("provider_metadata", {}).get("sources", [])))}
            rows[identifier] = value
        metadata = page.provider_metadata.to_dict()
        sources.update(metadata.get("sources", []))
        errors.extend(metadata.get("errors", []))
        for source, item in metadata.get("checkpoints", {}).items():
            record = progress.setdefault(source, {"ids": set(), "complete": False, "ordered": True})
            record["ids"].update(item["ids"])
            record["complete"] = item["complete"]
            record["ordered"] &= item["ordered"]
            record["cutoff"] = item.get("cutoff", False)
        cursor = page.next_cursor
        if not cursor:
            break
        if cursor in seen_cursors:
            errors.append({"source": "history", "error": "Repeated history cursor"})
            for item in progress.values():
                item["complete"] = False
            break
        seen_cursors.add(cursor)
    for source, item in progress.items():
        old = checkpoints.get(source, {})
        item["ids"] = sorted(set(old.get("ids", [])) | item["ids"])
        # An outage cannot establish a new complete frontier. Keep a previous
        # completed frontier usable, while making this refresh's errors visible.
        fresh_complete = item["complete"]
        item["complete"] = fresh_complete or bool(old.get("complete"))
        if not fresh_complete or item.get("cutoff"):
            item["ordered"] = item["ordered"] and old.get("ordered", True)
    ordered = sorted(rows.values(), key=lambda row: timestamp(row.get("timestamp")), reverse=True)
    progress = {**checkpoints, **progress}
    entry = {"matches": ordered, "sources": sorted(sources), "checkpoints": progress}
    client._history_store.put("history-v1", key, entry)
    reused = len(old_rows.keys() & rows.keys())
    metadata = {"sources": sorted(sources), "errors": errors,
                "cache": {"matches_reused": reused, "matches_added": len(rows.keys() - old_rows.keys()),
                          "provider_cutoffs": sorted(s for s, p in progress.items() if p.get("cutoff")),
                          "persistent": client._history_store.path is not None},
                "checkpoints": progress, "ordering": "descending"}
    metadata["errors"].extend({"source": "cache", "error": e} for e in client._history_store.errors)
    return MatchHistory({"matches": ordered, "next_cursor": None, "has_more": False,
                         "provider_metadata": metadata}, client=client)
