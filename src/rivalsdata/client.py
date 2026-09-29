"""HTTP client for RivalsData's public player API.

The upstream API is undocumented and may change. These routes were observed
from the site's public player page and search box.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests

from .exceptions import CloudflareError, PlayerNotFoundError, RivalsDataHTTPError
from .models import Player
from .resources import (
    Factions,
    Favorites,
    HeroStats,
    Insights,
    Leaderboards,
    Matches,
    Profiles,
    TeamUps,
)


class RivalsDataClient:
    """Access public player data from rivalsdata.com."""

    base_url = "https://rivalsdata.com"
    api_url = "https://api.rivalsdata.com"

    def __init__(
        self,
        *,
        timeout: float = 20,
        impersonate: str = "chrome",
        use_browser_fallback: bool = False,
    ) -> None:
        self.timeout = timeout
        self.impersonate = impersonate
        self.use_browser_fallback = use_browser_fallback
        self.session = requests.Session(impersonate=impersonate)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
            }
        )
        self.leaderboards = Leaderboards(self)
        self.heroes = HeroStats(self)
        self.team_ups = TeamUps(self)
        self.insights = Insights(self)
        self.factions = Factions(self)
        self.profiles = Profiles(self)
        self.favorites = Favorites(self)
        self.matches = Matches(self)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()

    def __enter__(self) -> RivalsDataClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def resolve_player(self, username: str) -> dict[str, Any]:
        """Search by username; add numeric uid to the source result."""
        query = username.strip()
        if not query:
            raise ValueError("username must not be empty")
        result = self._post_json("/players/search", {"name": query})
        if isinstance(result, dict):
            result = result.get("players", result.get("results", []))
        if not isinstance(result, list) or not result:
            raise PlayerNotFoundError(f"No player found for {username!r}")
        wanted = self._normalize_name(query)
        matches = [
            player for player in result
            if isinstance(player, dict)
            and self._normalize_name(str(player.get("name", ""))) == wanted
        ]
        player = (matches or [result[0]])[0]
        if not isinstance(player, dict):
            raise PlayerNotFoundError(f"No player found for {username!r}")
        uid = self._uid_from_search_result(player)
        if uid is None:
            raise RivalsDataHTTPError(
                "Search returned a player without a recognizable numeric UID"
            )
        return {**player, "uid": uid}

    def get_player(self, uuid_or_username: str | int) -> Player:
        """Fetch a typed public profile by numeric UID or username.

        Profile JSON keys are exposed as attributes (``player.level``), while
        subresources are lazy managers (``player.stats.maps(season=20)``).
        """
        value = str(uuid_or_username).strip()
        if not value:
            raise ValueError("uuid_or_username must not be empty")
        uid = value if value.isdecimal() else str(self.resolve_player(value)["uid"])
        result = self._post_json("/player", {"uid": int(uid)})
        if not isinstance(result, dict) or not result.get("uid"):
            raise PlayerNotFoundError(f"Player {value!r} was not found")
        return Player(result, self)

    def get_player_by_uid(self, uid: str | int) -> Player:
        """Fetch a profile by numeric UID."""
        if not str(uid).isdecimal():
            raise ValueError("uid must contain only digits")
        return self.get_player(uid)

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        response = self.session.get(
            f"{self.api_url}{path}", params=query, timeout=self.timeout
        )
        body = response.text
        blocked = (
            response.status_code in (403, 429, 503)
            or "cf-chl-" in body
            or "Just a moment" in body
        )
        if blocked:
            if not self.use_browser_fallback:
                raise CloudflareError(
                    "Cloudflare blocked this request. Install "
                    "rivalsdata-api[browser] and set use_browser_fallback=True."
                )
            return self._camoufox_get_json(path, query)
        if not response.ok:
            raise RivalsDataHTTPError(
                f"RivalsData API returned HTTP {response.status_code} for {path}: "
                f"{body[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise RivalsDataHTTPError(
                f"RivalsData API returned invalid JSON for {path}"
            ) from exc

    def _camoufox_get_json(self, path: str, params: dict[str, Any]) -> Any:
        try:
            from camoufox.sync_api import Camoufox
        except ImportError as exc:
            raise CloudflareError(
                "Install Camoufox with pip install 'rivalsdata-api[browser]' "
                "and run 'python -m camoufox fetch'."
            ) from exc
        query = urlencode(params)
        url = f"{self.api_url}{path}" + (f"?{query}" if query else "")
        try:
            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto(
                    self.base_url,
                    wait_until="domcontentloaded",
                    timeout=int(self.timeout * 1000),
                )
                response = page.evaluate(
                    """async ({url}) => {
                      const response = await fetch(url, {method: "GET"});
                      return {status: response.status, text: await response.text()};
                    }""",
                    {"url": url},
                )
        except Exception as exc:
            raise CloudflareError(f"Camoufox request failed: {exc}") from exc
        if response["status"] in (403, 429, 503) or "cf-chl-" in response["text"]:
            raise CloudflareError("Camoufox could not complete the API request")
        if response["status"] < 200 or response["status"] >= 300:
            raise RivalsDataHTTPError(
                f"RivalsData API returned HTTP {response['status']} for {path}: "
                f"{response['text'][:300]}"
            )
        try:
            return json.loads(response["text"])
        except json.JSONDecodeError as exc:
            raise RivalsDataHTTPError(
                f"RivalsData API returned invalid JSON for {path}"
            ) from exc

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.session.post(
            f"{self.api_url}{path}", json=payload, timeout=self.timeout
        )
        body = response.text
        blocked = (
            response.status_code in (403, 429, 503)
            or "cf-chl-" in body
            or "Just a moment" in body
        )
        if blocked:
            if not self.use_browser_fallback:
                raise CloudflareError(
                    "Cloudflare blocked this request. Install "
                    "rivalsdata-api[browser] and set use_browser_fallback=True."
                )
            return self._camoufox_post_json(path, payload)
        if not response.ok:
            raise RivalsDataHTTPError(
                f"RivalsData API returned HTTP {response.status_code} for {path}: "
                f"{body[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise RivalsDataHTTPError(
                f"RivalsData API returned invalid JSON for {path}"
            ) from exc

    def _camoufox_post_json(self, path: str, payload: dict[str, Any]) -> Any:
        """Retry an API POST from a browser context after loading the site."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError as exc:
            raise CloudflareError(
                "Install Camoufox with pip install 'rivalsdata-api[browser]' "
                "and run 'python -m camoufox fetch'."
            ) from exc
        try:
            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto(
                    self.base_url,
                    wait_until="domcontentloaded",
                    timeout=int(self.timeout * 1000),
                )
                response = page.evaluate(
                    """async ({url, payload}) => {
                      const response = await fetch(url, {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(payload)
                      });
                      return {
                        status: response.status,
                        text: await response.text()
                      };
                    }""",
                    {"url": f"{self.api_url}{path}", "payload": payload},
                )
        except Exception as exc:
            raise CloudflareError(f"Camoufox request failed: {exc}") from exc
        if (
            response["status"] in (403, 429, 503)
            or "cf-chl-" in response["text"]
        ):
            raise CloudflareError("Camoufox could not complete the API request")
        if response["status"] < 200 or response["status"] >= 300:
            raise RivalsDataHTTPError(
                f"RivalsData API returned HTTP {response['status']} for {path}: "
                f"{response['text'][:300]}"
            )
        try:
            return json.loads(response["text"])
        except json.JSONDecodeError as exc:
            raise RivalsDataHTTPError(
                f"RivalsData API returned invalid JSON for {path}"
            ) from exc

    @staticmethod
    def _uid_from_search_result(player: dict[str, Any]) -> int | None:
        for key in ("uid", "uuid", "playerId", "player_id"):
            value = player.get(key)
            if value is not None and str(value).isdecimal():
                return int(value)
        suffix = str(player.get("aid", "")).rsplit("_", 1)[-1]
        return int(suffix) if suffix.isdecimal() else None

    @staticmethod
    def _normalize_name(name: str) -> str:
        return unicodedata.normalize("NFKC", name).casefold().strip()
