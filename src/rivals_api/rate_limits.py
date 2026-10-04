"""Process-wide provider pacing and server-directed rate-limit cooldowns."""

from __future__ import annotations

import math
import time
from email.utils import parsedate_to_datetime
from threading import RLock

from .exceptions import RivalsDataHTTPError


def setting(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return float(value)


def retry_after(value):
    try:
        seconds = float(value)
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            return max(0, date.timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            return None


def limited(source, delay):
    error = RivalsDataHTTPError(
        f"{source} rate limited the request (HTTP 429); retry after {math.ceil(delay)} seconds")
    error.status_code = 429
    error.retry_after = max(0, delay)
    return error


class RateGate:
    def __init__(self, source):
        self.source = source
        self.lock = RLock()
        self.next_request = self.blocked_until = 0.0
        self.failures = 0

    def run(self, request, *, interval=1, cooldown=30):
        # Keep the lock through the response so queued callers see a newly
        # established cooldown before sending their own request.
        with self.lock:
            now = time.monotonic()
            if self.blocked_until > now:
                raise limited(self.source, self.blocked_until - now)
            delay = self.next_request - now
            if delay > 0:
                time.sleep(delay)
            try:
                response = request()
            finally:
                self.next_request = time.monotonic() + interval
            if isinstance(response, dict):
                status, headers = response.get("status"), response.get("headers", {})
            elif isinstance(response, tuple):
                status, headers = response[0], {}
            else:
                status = response.status_code
                headers = getattr(response, "headers", {})
            if status == 429:
                self.failures += 1
                server_delay = retry_after((headers or {}).get("Retry-After", (headers or {}).get("retry-after")))
                delay = max(interval, server_delay if server_delay is not None
                            else min(300, cooldown * 2 ** min(self.failures - 1, 8)))
                self.blocked_until = time.monotonic() + delay
                raise limited(self.source, delay)
            if status is not None and 200 <= status < 300:
                self.failures = 0
            return response


_GATES = {}
_LOCK = RLock()


def gate(origin):
    with _LOCK:
        return _GATES.setdefault(origin, RateGate(origin))
