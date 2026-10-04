"""Read-only transports for the observed public provider contracts."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests

from .exceptions import CloudflareError, PrivacyError, RivalsDataHTTPError


class ProviderTransport:
    """Independent origin/session, bounded cache, and optional Camoufox fallback."""

    def __init__(self, name: str, api: str, origin: str, owner: Any) -> None:
        from .rate_limits import gate

        self._rate_gate = gate(api)
        self.name, self.api, self.origin, self.owner = name, api, origin, owner
        self.session = requests.Session(impersonate=owner.impersonate)
        self.session.headers.update({"Accept": "application/json",
                                     "Origin": origin, "Referer": origin + "/"})
        self._cache: dict[str, tuple[float, Any]] = {}
        self._browser_context = None
        self._page = None

    def close(self) -> None:
        self.session.close()
        self._cache.clear()
        if self._browser_context is not None:
            self._browser_context.__exit__(None, None, None)
            self._browser_context = self._page = None

    def request(self, path: str, *, params: dict | None = None,
                payload: dict | None = None, refresh: bool = False) -> Any:
        # POST is only used for the provider's read-only name search.
        if payload is not None and (self.name != "rivalstracker" or path != "/find-player"):
            raise ValueError("Only read-only provider requests are supported")
        params = {k: v for k, v in (params or {}).items() if v is not None}
        key = json.dumps([path, params, payload], sort_keys=True)
        cached = self._cache.get(key)
        if cached and not refresh and time.monotonic() - cached[0] < self.owner.provider_cache_ttl:
            return deepcopy(cached[1])
        try:
            if payload is None:
                request = lambda: self.session.get(self.api + path, params=params, timeout=self.owner.timeout)
            else:
                request = lambda: self.session.post(self.api + path, json=payload, timeout=self.owner.timeout)
            response = self._rate_gate.run(request, interval=self.owner.request_interval,
                                           cooldown=self.owner.rate_limit_cooldown)
        except requests.exceptions.RequestException as exc:
            raise RivalsDataHTTPError(f"{self.name} request failed: {exc}") from exc
        body, status = response.text, response.status_code
        if status == 403 and "private" in body.lower() and body.lstrip().startswith("{"):
            raise PrivacyError(f"{self.name} profile section is private")
        if status == 429:
            raise RivalsDataHTTPError(f"{self.name} rate limited the request (HTTP 429)")
        if status in (403, 503) or "cf-chl-" in body or "Just a moment" in body:
            if not self.owner.use_browser_fallback:
                raise CloudflareError(f"{self.name} requires use_browser_fallback=True")
            status, body = self._rate_gate.run(lambda: self._browser(path, params, payload),
                                               interval=self.owner.request_interval,
                                               cooldown=self.owner.rate_limit_cooldown)
        if not 200 <= status < 300:
            raise RivalsDataHTTPError(f"{self.name} HTTP {status} for {path}: {body[:200]}")
        try:
            result = json.loads(body)
        except ValueError as exc:
            raise RivalsDataHTTPError(f"{self.name} returned invalid JSON for {path}") from exc
        if self.name == "tracker":
            if not isinstance(result, dict) or "data" not in result:
                raise RivalsDataHTTPError("Tracker returned an invalid data envelope")
            result = result["data"]
        if len(self._cache) >= 128:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = time.monotonic(), deepcopy(result)
        return result

    def _browser(self, path: str, params: dict, payload: dict | None) -> tuple[int, str] | dict:
        try:
            from camoufox.sync_api import Camoufox

            url = self.api + path + ("?" + urlencode(params) if params else "")
            if self._page is None:
                context = Camoufox(headless=True)
                browser = context.__enter__()
                self._browser_context = context
                self._page = browser.new_page()
                self._page.goto(self.origin, wait_until="domcontentloaded",
                                timeout=int(self.owner.timeout * 1000))
            result = self._page.evaluate("""async ({url, payload, timeout}) => {
                  const controller = new AbortController();
                  const timer = setTimeout(() => controller.abort(), timeout);
                  try {
                    const r = await fetch(url, {credentials: 'include',
                      signal: controller.signal, method: payload ? 'POST' : 'GET',
                      ...(payload ? {headers: {'Content-Type':'application/json'},
                        body: JSON.stringify(payload)} : {})});
                    return {status:r.status, text:await r.text(), headers: {
                      'Retry-After': r.headers.get('Retry-After')}};
                  } finally {clearTimeout(timer);}
                }""", {"url": url, "payload": payload,
                         "timeout": int(self.owner.timeout * 1000)})
            if result["status"] == 429:
                # Pass browser headers to the same gate used for HTTP requests.
                return result
            return result["status"], result["text"]
        except ImportError as exc:
            raise CloudflareError("Install rivals-api[browser] and fetch Camoufox") from exc
        except Exception as exc:
            raise CloudflareError(f"{self.name} Camoufox request failed: {exc}") from exc


class Providers:
    def __init__(self, owner: Any) -> None:
        self.rt = ProviderTransport("rivalstracker", "https://api.rivalstracker.com/api",
                                    "https://rivalstracker.com", owner)
        self.tracker = ProviderTransport("tracker", "https://api.tracker.gg",
                                         "https://tracker.gg/marvel-rivals", owner)

    def close(self) -> None:
        self.rt.close()
        self.tracker.close()
