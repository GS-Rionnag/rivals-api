"""Client for public Marvel Rivals data from multiple tracker providers.

RivalsData, RivalsTracker, and Tracker.gg endpoints are unofficial or
undocumented and may change. See the provider integration documentation.
"""

from __future__ import annotations

import json
import time
import unicodedata
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests

from .exceptions import (
    CloudflareError,
    PlayerNotFoundError,
    PrivacyError,
    RivalsDataError,
    RivalsDataHTTPError,
)
from .models import Player, PlayerSearchResult
from .normalize import merge, rt_profile, tracker_stats
from .providers import Providers
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

_MATCH_HISTORY_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_MATCH_DETAIL_CACHE: dict[tuple[str, bool], dict[str, Any]] = {}


class RivalsClient:
    """Access and compare public Marvel Rivals data across providers."""

    base_url = "https://rivalsdata.com"
    api_url = "https://api.rivalsdata.com"

    leaderboards: Leaderboards
    heroes: HeroStats
    team_ups: TeamUps
    insights: Insights
    factions: Factions
    profiles: Profiles
    favorites: Favorites
    matches: Matches

    def __init__(
        self,
        *,
        timeout: float = 20,
        impersonate: str = "chrome",
        use_browser_fallback: bool = False,
        enrich: bool = True,
        provider_cache_ttl: float = 60,
    ) -> None:
        self.timeout = timeout
        self.impersonate = impersonate
        self.use_browser_fallback = use_browser_fallback
        self.enrich = enrich
        self.provider_cache_ttl = provider_cache_ttl
        self.providers = Providers(self)
        self._player_names: dict[int, str] = {}
        self._match_history_cache = _MATCH_HISTORY_CACHE
        self._match_detail_cache = _MATCH_DETAIL_CACHE
        self.provider_errors: list[dict[str, str]] = []
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
        from .extensions import Community, GameAnalytics

        self.analytics = GameAnalytics(self)
        self.community = Community(self)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()
        self.providers.close()

    def __enter__(self) -> RivalsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request_with_gateway_retries(
        self, method: Any, path: str, **kwargs: Any
    ) -> Any:
        """Retry short-lived upstream gateway failures on read-only requests."""
        url = f"{self.api_url}{path}"
        for attempt in range(3):
            try:
                response = method(url, timeout=self.timeout, **kwargs)
            except requests.exceptions.RequestException as exc:
                raise RivalsDataHTTPError(f"RivalsData request failed for {path}: {exc}") from exc
            if response.status_code not in (502, 504) or attempt == 2:
                break
            time.sleep(0.25 * (attempt + 1))
        return response

    def resolve_player(self, username: str) -> PlayerSearchResult:
        """Search by username; add numeric uid to the source result."""
        query = username.strip()
        if not query:
            raise ValueError("username must not be empty")
        try:
            result = self._post_json("/players/search", {"name": query})
        except RivalsDataError:
            if not self.enrich:
                raise
            result = self.providers.rt.request("/find-player", payload={"name": query})
            # Provider fallback must never silently resolve a fuzzy candidate.
            result = [row for row in result if isinstance(row, dict)
                      and self._normalize_name(str(row.get("name", "")))
                      == self._normalize_name(query)]
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
        return PlayerSearchResult({**player, "uid": uid})

    def search_players(self, name: str) -> list[PlayerSearchResult]:
        """Return all provider search candidates, deduplicated by game UID."""
        if not name.strip():
            raise ValueError("name must not be empty")
        results = self.providers.rt.request("/find-player", payload={"name": name.strip()})
        found = {}
        for row in results:
            uid = self._uid_from_search_result(row)
            if uid is not None:
                found[uid] = PlayerSearchResult({**row, "uid": uid})
        return list(found.values())

    def _optional_provider(self, source: str, path: str, **kwargs: Any) -> Any:
        """Supplementary outages do not erase a successful primary response."""
        if not self.enrich:
            return None
        try:
            return getattr(self.providers, source).request(path, **kwargs)
        except RivalsDataError as exc:
            self.provider_errors.append({"source": source, "path": path, "error": str(exc)})
            self.provider_errors[:] = self.provider_errors[-100:]
            return None

    def _rt_player(self, uid: int, season: Any = None) -> Any:
        body = self._optional_provider("rt", f"/player/{uid}", params={"season": season})
        if (isinstance(body, dict) and isinstance(body.get("player"), dict)
                and str(body["player"].get("_id")) == str(uid)):
            return body
        return None

    def _tracker_path(self, uid: int) -> str:
        from urllib.parse import quote

        name = self._player_names.get(uid)
        if not name:
            name = self.get_player(uid).get("name")
        if not name:
            raise PlayerNotFoundError("No verified in-game name for this UID")
        return "/api/v2/marvel-rivals/standard/profile/ign/" + quote(name, safe="")

    def get_player(self, uuid_or_username: str | int) -> Player:
        """Fetch a typed public profile by numeric UID or username.

        Profile JSON keys are exposed as attributes (``player.level``), while
        subresources are lazy managers (``player.stats.maps(season=20)``).
        """
        value = str(uuid_or_username).strip()
        if not value:
            raise ValueError("uuid_or_username must not be empty")
        uid = value if value.isdecimal() else str(self.resolve_player(value)["uid"])
        try:
            result = self._post_json("/player", {"uid": int(uid)})
            if self.enrich and isinstance(result, dict):
                result.setdefault("provider_metadata", {"sources": ["rivalsdata"]})
                result["provider_metadata"].setdefault("evidence", {})["rivalsdata"] = {
                    "kind": "profile", "scope": {"uid": int(uid)},
                    "updated_at": result.get("cached_at")}
        except RivalsDataError:
            if not self.enrich:
                raise
            body = self.providers.rt.request(f"/player/{uid}")
            result = rt_profile(body)
        if not isinstance(result, dict) or str(result.get("uid")) != uid:
            raise PlayerNotFoundError(f"Player {value!r} was not found")
        body = self._rt_player(int(uid))
        if body and str(body.get("player", {}).get("_id")) == uid:
            result = merge(result, rt_profile(body), "rivalstracker")
        if result.get("name"):
            self._player_names[int(uid)] = result["name"]
        if self.enrich:
            self._select_career_summary(result, int(uid))
        return Player(result, self)

    def _select_career_summary(self, result: dict, uid: int) -> None:
        """Canonical career counts are distinct from raw rank-system counts."""
        ranks = result.get("rank_game_season", {})
        seasons = [row.get("rank_game_id") for key, row in ranks.items()
                   if str(key).startswith("1001") and isinstance(row, dict)
                   and isinstance(row.get("rank_game_id"), int)]
        if not seasons or uid not in self._player_names:
            return
        season = max(seasons)
        body = self._rt_player(uid, season)
        stats = body.get("stats", {}) if body else {}
        games, wins = stats.get("ranked_matches"), stats.get("ranked_matches_wins")
        summary = {}
        scope = {"uid": uid, "season": season, "mode": "competitive", "counts_basis": "career_matches"}
        if isinstance(games, (int, float)) and isinstance(wins, (int, float)) and 0 <= wins <= games:
            summary = {"games": games, "wins": wins, "losses": games - wins,
                       "provider_metadata": {"sources": ["rivalstracker"], "evidence": {
                           "rivalstracker": {"kind": "career", "scope": scope}}}}
        segments = self._optional_provider("tracker", self._tracker_path(uid) + "/segments/career",
                                           params={"mode": "competitive", "season": season})
        for segment in segments or []:
            attrs = segment.get("attributes", {})
            if (segment.get("type") != "overview" or attrs.get("mode") != "competitive"
                    or str(attrs.get("season")) != str(season)):
                continue
            values = tracker_stats(segment)
            games, wins = values.get("matchesPlayed"), values.get("matchesWon")
            if not isinstance(games, (int, float)) or not isinstance(wins, (int, float)):
                continue
            summary = merge(summary, {"games": games, "wins": wins, "losses": games - wins}, "tracker",
                            context={"kind": "career", "scope": scope})
        if summary and summary.get("games") is not None:
            result["career_summary"] = {"season": season, "competitive": summary,
                                        "counts_basis": "career_matches"}

    def get_player_by_uid(self, uid: str | int) -> Player:
        """Fetch a profile by numeric UID."""
        if not str(uid).isdecimal():
            raise ValueError("uid must contain only digits")
        return self.get_player(uid)

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        response = self._request_with_gateway_retries(
            self.session.get, path, params=query
        )
        body = response.text
        if response.status_code == 429:
            raise RivalsDataHTTPError(f"RivalsData rate limited the request for {path} (HTTP 429)")
        if response.status_code == 403 and body.lstrip().startswith("{") and "private" in body.lower():
            raise PrivacyError(f"RivalsData section is private: {path}")
        blocked = (
            response.status_code in (403, 429, 503)
            or "cf-chl-" in body
            or "Just a moment" in body
        )
        if blocked:
            if not self.use_browser_fallback:
                raise CloudflareError(
                    "Cloudflare blocked this request. Install "
                    "rivals-api[browser] and set use_browser_fallback=True."
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
                "Install Camoufox with pip install 'rivals-api[browser]' "
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
        response = self._request_with_gateway_retries(
            self.session.post, path, json=payload
        )
        body = response.text
        if response.status_code == 429:
            raise RivalsDataHTTPError(f"RivalsData rate limited the request for {path} (HTTP 429)")
        if response.status_code == 403 and body.lstrip().startswith("{") and "private" in body.lower():
            raise PrivacyError(f"RivalsData section is private: {path}")
        blocked = (
            response.status_code in (403, 429, 503)
            or "cf-chl-" in body
            or "Just a moment" in body
        )
        if blocked:
            if not self.use_browser_fallback:
                raise CloudflareError(
                    "Cloudflare blocked this request. Install "
                    "rivals-api[browser] and set use_browser_fallback=True."
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
                "Install Camoufox with pip install 'rivals-api[browser]' "
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
