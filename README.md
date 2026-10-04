# rivals-api

An unofficial, multi-source Python tracker for public Marvel Rivals data. It
combines RivalsData, RivalsTracker, and Tracker.gg, keeps source disagreements
visible, and preserves unfamiliar response fields as providers change. The
project also includes a read-only MCP server.

## Install

Python 3.10 or newer:

```console
python -m pip install rivals-api
```

For editable development, clone the repository and run
`python -m pip install -e '.[dev]'`. The optional Camoufox Cloudflare fallback
is installed with `python -m pip install 'rivals-api[browser]'`, followed
by `python -m camoufox fetch`.

## Quick start

```python
from rivals_api import RivalsClient, hero_id, hero_name

print(hero_name(1016))  # Loki
print(hero_id("Loki"))  # 1016

with RivalsClient() as rd:
    player = rd.get_player("GS-")  # numeric UID works too
    print(player.name, player.level, player.rank_game_season)
    print(player.stats.win_rate().win_rate_pct)  # Current season: Competitive + Quickplay

    # Player profile sections are lazy resource managers.
    hero_season = player.heroes.fetch(season=20)
    all_hero_seasons = player.heroes.fetch(season="all")
    map_stats = player.stats.maps(season=20)
    match_page = player.matches.fetch(limit=20, season=20)
    all_matches = player.matches.fetch(limit="all")
    season_rate = player.stats.win_rate()
    competitive_rate = player.stats.win_rate(mode="competitive", season=20)
    print(season_rate.win_rate_pct, season_rate.metadata.coverage)
    hero_rates = player.stats.hero_win_rates()
    class_rates = player.stats.class_win_rates()

    # Current match when its provider exposes it; Custom discovery is unsupported.
    live_game = player.live_game.fetch()
    if live_game is not None:
        print(live_game.players, live_game.team_avg_rank)

    # Site-wide resources are available from the client.
    leaderboard = rd.leaderboards.fetch(limit=100, season=20, platform=1)
    tier_list = rd.heroes.tier_list(platform=1, rank="grandmaster_plus")
    team_ups = rd.team_ups.fetch(platform=1, rank="grandmaster_plus")
    xp_page = rd.insights.xp()

print(hero_season[0].win_rate)  # integer percent when wins/losses are present
```

`RivalsDataClient` remains an alias for `RivalsClient`. The old `rivalsdata`
import path is also retained for existing projects. To migrate an existing
installation, uninstall `rivalsdata-api` first, then install `rivals-api`;
this avoids the two distributions sharing the compatibility-package files.

Use `player.stats.win_rate()` for the canonical season win rate. Overall,
hero, and class requests accept `mode="competitive"`, `"quickplay"`, or `"all"`;
**the default is `"all"`, meaning Competitive plus Quickplay**. Custom, Arcade,
and other queues are excluded. Omitted season resolves the current season;
a numeric season selects that season. `season="all"` is a separate selector
for all available seasons.

Use the same season selector for overall, hero, and class data:

```python
current = player.stats.win_rate(season="current")  # Same as omitting season
one_season = player.stats.win_rate(season=20)      # Provider ID, not display number
all_seasons = player.stats.win_rate(season="all")
season_heroes = player.stats.hero_win_rates(season=20)
season_classes = player.stats.class_win_rates(season=20)
all_heroes = player.stats.hero_win_rates(season="all")
all_classes = player.stats.class_win_rates(season="all")
catalog = player.analytics.seasons()  # Maps provider IDs to season display names
```

MCP `get_player_win_rate`, `get_player_hero_win_rates`,
`get_player_class_win_rates`, and `get_player_heroes` accept these same selectors.
Mode is independent of season and still defaults to `"all"`.
Current-season detection tries Tracker.gg's `currentSeason`, then RivalsTracker's
global hero-stat season if Tracker metadata is unavailable. If neither can
verify it, supply a known positive season ID or explicitly request `"all"`.
The client never silently changes a current-season request to all seasons.
All-seasons calculations cover available tracked history; they do not promise
complete lifetime coverage.

```python
rate = player.stats.win_rate()  # Current season, Competitive plus Quickplay
ranked = player.stats.win_rate(mode="competitive")
quickplay = player.stats.win_rate(mode="quickplay", season=20)
print(rate.wins, rate.games, rate.win_rate_pct)
print(rate.metadata.by_mode, rate.metadata.coverage)
```

All three win-rate functions default to `method="normal"`, which reads provider
summaries without requesting match history or match details. Overall rates
prefer direct career counts, then map totals, then explicitly marked rank-system
counts. Hero rates select an intact provider dataset; class rates use that
dataset's class totals or compatible direct role records. Provider percentages
are never averaged. Combined modes sum counts before division. Selection,
disagreements, missing modes, and counting bases remain visible in metadata.
If one requested mode has no overall counts, the complete-scope overall fields
remain null; `partial_result` exposes the available counts/rate and
`included_modes` explicitly. Consumers may display that result with a coverage
notice. A failed provider does not discard valid results from other providers.
Hero participation counts can differ from unique match counts, especially when
players switch heroes; normal results cannot guarantee the precise result.

The old `player.win_rate` property and profile-overview `win_rate` field remain
competitive profile snapshots for compatibility. They do not invoke the new
season/history verification. Use `player.stats.win_rate()` or MCP
`get_player_win_rate` for the canonical selectable season calculation.

Ordinary hero and class requests need no calculation-method argument:

```python
heroes = player.stats.heroes()  # Current season, both modes, most played first
classes = player.stats.classes()
for hero in heroes:
    print(hero.name, hero.games, hero.wins, hero.losses, hero.win_rate_pct)

quickplay = player.stats.heroes(mode="quickplay", season="all")
rates = player.stats.hero_win_rates()  # Envelope retains coverage for empty lists
print(rates.metadata.coverage)
print(rates.metadata.unresolved)
```

`player.heroes.fetch()` uses the same calculation. `get_player_heroes` and
`get_player_stats(category="heroes")` return a `data` list plus `metadata`;
all win-rate MCP tools accept `method="normal"` or `"precise"`. All default to
Competitive plus Quickplay and resolve the current season from live Tracker profile metadata.
If that season cannot be verified, supply a numeric season or `"all"`.
`"all"` means all available tracked history, not guaranteed lifetime coverage.
Class responses retain `.classes`, with direct counts and the selected mode's
nested counts; hero rows likewise retain the selected mode's nested stats.

Use `method="precise"` to traverse all available history and verify completed
match outcomes. Hero and class rates assign each match once to its longest-played
hero and that hero's class; overall outcomes do not require hero playtime.

```python
overall = player.stats.win_rate(season=20, method="precise")
heroes = player.stats.hero_win_rates(season=20, method="precise")
classes = player.stats.class_win_rates(season=20, method="precise")
print(overall.metadata.cache)
```

Match details supply per-hero seconds. Complete provider records are compared
independently: durations are never blended across sources. Missing/invalid
playtime, equal maximum playtimes, ambiguous identity, conflicting longest
heroes, and unknown/conflicting outcomes remain unresolved. There is no
summary-hero fallback. Coverage reports found, attributed, and unresolved
matches; it never claims complete game history. `play_time` is the assigned
hero's playtime in its attributed matches, not total lifetime hero playtime.

The first precise request can load every history page and match detail. History
and details persist in SQLite across client restarts. Later requests refresh each
provider's newest pages, stop when they encounter a retained match on a previously
completed, chronological traversal, and combine new matches with the cached tail.
Each provider has its own stopping point. Interrupted or unordered traversals
do not establish a stopping point. Missing or incomplete details are retried.
This assumes providers do not backfill older history behind the cached boundary;
available tracked history still cannot guarantee complete game history.

Short-lived calculation caches use `provider_cache_ttl` (60 seconds by default).
Fully failed normal calculations are reused for five seconds across the three
win-rate functions. After a provider returns HTTP 429, remaining summary requests
to that provider are skipped for the calculation; other providers still run.
HTTP and browser API requests share a process-wide guard per provider, including
across client instances and client restarts within that process. Requests are
serialized and spaced at least one second apart by default, with additional
random delay up to 25% of the interval (capped at one second). HTTP 429 establishes a
cooldown using `Retry-After` (seconds or HTTP date), or 30 seconds with exponential
backoff up to five minutes when the header is absent. Requests during cooldown
fail locally without hitting the provider; valid cached responses remain usable.
The error exposes `status_code=429` and `retry_after` seconds. Browser fallback
does not bypass cooldowns. Configure `request_interval` and `rate_limit_cooldown`
on `RivalsClient`; the guard is not shared between separate processes or hosts.
Provider limits can still be exceeded by other traffic or stricter limits.
Pass `RivalsClient(cache_dir="path/to/cache")` to choose the persistent location,
or set `RIVALS_API_CACHE_DIR`. The default is the user's local application cache.
`persist_cache=False` keeps evidence only in memory for that client. To rebuild
the retained history from scratch, close clients and remove `matches.sqlite3`
from that cache directory. `client.matches.get(id, refresh=True)` refreshes a
specific completed detail when necessary.

For the old provider-summary definitions, use `player.heroes.summary()`,
`player.stats.summary_heroes(mode="competitive")`, or
`player.stats.summary_classes()`. These retain provider participation counts,
combat fields, and leaderboard ranks; they have different attribution rules.
Canonical rows do not invent leaderboard ranks and expose `rank=None`.

Character playtime was checked with Camoufox on 2026-09-30. Player hero stats
did not expose cumulative hours, including in All Seasons. Match details do
provide seconds in `match.teams[].players[].heroes[].play_time`; the site shows
these as minutes and seconds when hovering a hero portrait. Sum the relevant
player's entries across distinct retrieved matches and divide by 3600 to get
character hours for those matches. Incomplete history prevents treating this as
a lifetime total. See [the playtime investigation](docs/API.md#character-playtime-investigation-2026-09-30)
for the observed fields and example.

## MCP server (ChatGPT and Claude)

Install the MCP extra and the package:

```console
python -m pip install 'rivals-api[mcp]'
```

The server exposes read-only tools for player search and profiles, a player's
current live match (when they are in one), match history, player stats,
leaderboards, heroes, team-ups, public insights, matches, and factions. The
`show_player_dashboard` tool returns an MCP-UI player card with rank and
competitive record plus one optional data section per call: current match
roster, hero win-rate chart, or recent match form with K/D/A. This keeps each
dashboard pull to the profile plus one selected data section. Provider enrichment
can make additional requests to compare the reported values. It supports
local stdio for Claude Desktop
and Streamable HTTP for remote MCP clients such as ChatGPT. Data comes from
public provider endpoints and may be incomplete, private, or stale. Live
Custom-game discovery is not currently implemented.

Known `hero_id` and `top_hero_id` fields in MCP results include corresponding
`hero_name` and `top_hero_name` fields. The `resolve_hero` tool accepts either
a hero name or numeric ID. The pip package also exports `hero_name(id)` and
`hero_id(name)`; returned `DataModel` rows provide `.hero_name` and
`.top_hero_name` conveniences. Those resolved fields are included in mapping
iteration and `.to_dict()` output to simplify serialization; `.raw` remains the
untouched source payload.

### How the MCP UI works

`show_player_dashboard` fetches current data, then returns an HTML UI resource
alongside the tool result. It advertises the dashboard through
`_meta.ui.resourceUri`, uses the `text/html;profile=mcp-app` resource MIME type,
and registers that URI for `resources/read` so the host can actually load the
app frame. The tool result carries the rendered dashboard as structured content
for the app frame and an embedded HTML resource for older MCP-UI clients. It
also includes `openai/outputTemplate` as a ChatGPT compatibility alias. Hosts
without UI support still receive a text result and can use the regular MCP
tools. The dashboard is a snapshot from the time the tool runs; ask for it
again to refresh.
The `section` argument defaults to `live_match`; use `hero_form` or
`recent_matches` in separate calls when you need those views.

### Claude Desktop (local)

Add a server entry to Claude Desktop's `claude_desktop_config.json`, replacing
the path with the Python executable in the environment where the extra is
installed:

```json
{
  "mcpServers": {
    "rivals-api": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "rivals_api.mcp_server"]
    }
  }
}
```

On macOS/Linux, use the environment's `bin/python` path. Restart Claude Desktop
after saving the configuration.

### ChatGPT or remote Claude connector

Run the server on a host reachable over HTTPS:

```console
uvicorn rivals_api.mcp_server:app --host 0.0.0.0 --port 8000
```

The MCP endpoint is `/mcp` (for example, `https://your-host.example/mcp`). Add
that endpoint through the client's custom/remote MCP connector settings. The
server does not implement authentication; put it behind an authenticated
HTTPS gateway before exposing it publicly. For local development, bind to
`127.0.0.1` instead. The `app` is the MCP SDK's Streamable HTTP ASGI
application; Uvicorn manages its lifespan and session manager.

Every implemented response route now has named endpoint models and row models
with annotations for fields observed in the API inventory. This includes
`Player`, `Match`, `MatchHistory`, `MatchTeam`, `MatchPlayer`, `Character`,
`ProficiencyResponse`, `LeaderboardResponse`, `PunishmentsPage`, `XPPage`,
`Top500Response`, and typed teammate, crosshair, stats, faction, and insight
records. For example, `rd.matches.get(match_id)` returns a `Match`,
`player.matches.fetch(limit=...)` returns a `MatchHistory`. The required limit
is either a positive number (bounded fetch with a resumable cursor) or
`"all"` (fetch every available page); both combine and deduplicate providers.
Each history row is a client-bound `Match`. Call `get_details()` while its
client is open to lazily fetch combined RivalsData, RivalsTracker, and Tracker.gg
details, including typed teams, players, and hero segments:

```python
with RivalsClient(use_browser_fallback=True) as client:
    player = client.get_player(1970288503)
    history = player.matches.fetch(limit=20)
    if history.matches:
        match = history.matches[0]
        details = match.get_details()  # Match; the history row stays unchanged
        for team in details.teams:
            for participant in team.players:
                print(participant.name, participant.get("accuracy_percent"))
        print(details.provider_metadata.errors)
        # match.get_details(refresh=True) bypasses detail/provider caches.
```

`client.matches.get(match_id, refresh=False)` uses the same fetcher. Provider
outages return available details with errors; conflicts and field selections
remain in `provider_metadata`. `accuracy_percent` uses percent units for players
and heroes. The legacy RD `accuracy` field remains a player percentage or a
hero ratio; `session_hit_rate` is separate and is never substituted for accuracy.
Unknown/NaN accuracy is unavailable. See the
[match detail guide](docs/PROVIDER_INTEGRATION.md#combined-match-details).

History and detail matches also expose readable typed references. They format
as names in bot messages; use `.name` for a plain string and `.id` for the
original identifier. For a match with map ID `1288`, mode `3`, and platform `1`:

```python
print(match.map)                # Hell's Heaven
print(match.map.name)           # Hell's Heaven (str)
print(match.map.id)             # 1288
print(match.map.location)       # Hydra Charteris Base
print(match.game_mode)          # Custom
print(match.gameplay_mode)      # Domination
print(match.platform)           # PC
print(match.hero)               # Named Character, when history includes a hero
print(match.rank)               # Named Rank, when a rank level is available
print(match.season_info)        # Named Season, when a season is available
```

These are objects with `__str__`, so `f"Played on {match.map}"` prints the map
name while `match.map.id` remains available. `game_play_mode` aliases
`gameplay_mode`. Participants expose `hero`, `top_hero`, `rank_info`, and
`platform_info`; draft entries expose `hero` and `team`. Existing Character
records now have `.id`, `.name`, and name-based string formatting.

**Migration:** `match.platform` is now a `Platform` object. Use
`match.platform_id` or `match.platform.id` for its previous numeric value.
`to_dict()` serializes references as `{id, name, is_known, source, ...}` objects;
the original `map_id`, `game_mode_id`, and other numeric fields remain present.
`.raw` preserves the input payload. The packaged catalogs resolve names
without additional network requests. Unmapped codes produce an explicit
`Unknown ...` reference with `is_known=False`; absent fields return `None`.
See [readable match references](docs/GAME_REFERENCES.md) for mapping sources
and gameplay-code limits.

Hero/class requests use the canonical longest-played-hero calculation described
above. The Python `matches.fetch_hero_win_rates()` and
`matches.fetch_class_win_rates()` names remain compatibility aliases by default.
Explicit legacy `method="estimate"` with a single mode retains summary estimates; `method="cached"`
uses already-cached details without requests and leaves unverifiable matches
unresolved. These overrides are not exposed by the hero/class MCP tools.
Overall `matches.fetch_win_rate()` aliases the new season calculation. Explicit
legacy method overrides remain available in Python, but the MCP overall tool
now accepts only player, season, and mode. Its default mode is also `"all"`.
`player.proficiency.fetch()` returns a
`ProficiencyResponse`. Nested match
teams and participants are converted to `MatchTeam` and `MatchPlayer`; embedded
character records use `Character`. Models support mapping access
(`player["level"]`) and attribute access (`player.level`). Unknown upstream
fields are still preserved and available through `.raw`; endpoint schemas
that have not been observed completely are annotated only for known fields.

```python
with RivalsClient() as rd:
    player = rd.get_player(1970288503)             # Player
    proficiency = player.proficiency.fetch()       # ProficiencyResponse
    account = next(iter(proficiency.accounts.values()))  # Proficiency
    hero = account.hero_proficiency_infos["1011"]   # HeroProficiency
    print(hero.proficiency_level, hero.proficiency_point)

    tier_list = rd.heroes.tier_list()               # TierListResponse
    print(tier_list.heroes[0].hero_id)             # Character
```

## Public resources

For a player selection list, use `rd.search_players("silo")`, or the MCP tool
`search_players(name="silo")`. Each candidate includes a name and numeric UID;
pass the selected UID to `get_player_profile(uid=283622404)` for their profile
overview. `search_player_candidates` remains an alias, and `get_player` still
accepts a UID or exact name. MCP `search_players` now returns a list instead
of one resolved account. Live checks on 2026-10-02 confirmed that the
candidate search includes `siloء` (UID `283622404`) when searching `silo`.
See [the player-search audit](docs/PLAYER_SEARCH_AUDIT.md) for provider comparisons
and exact-name versus suggestion behavior.

- `rd.leaderboards.fetch(...)` — global player ranking.
- `rd.heroes.tier_list(...)`, `.get(hero_id)`, `.meta(hero_id, range=90)`,
  `.leaderboard(hero_id, **filters)` — hero metrics and ranking.
- `rd.team_ups.fetch(...)` — team-up stats.
- `rd.insights.punishments(...)`, `.xp(...)`, `.top_500(...)`, `.commbans(...)`,
  `.leavers(...)` — public insights and cursor metadata.
- `rd.factions.get(faction_id)`, `rd.matches.get(match_id)`,
  `rd.profiles.get(username)`, and `rd.favorites.fetch(uids)` — detail/profile
  lookups.
- `player.heroes.fetch(...)`, `.matches.fetch(...)`, `.live_game.fetch()`, `.teammates.fetch(...)`,
  `.crosshairs.fetch()`, `.proficiency.fetch()`, `.punishments.fetch()`,
  `.name_history.fetch()` — profile sections.
- `player.stats.heroes(...)`, `.maps(...)`, `.bans(...)` — detailed profile stats.

See [the observed API inventory](docs/API.md) for methods, parameters, observed
response shapes, and endpoints that require a RivalsData account. The API
inventory distinguishes observed behavior from inferred/unverified details.

## Cloudflare fallback

Requests use curl_cffi with a Chrome TLS profile by default. If blocked, enable
the optional browser fallback:

```python
with RivalsClient(use_browser_fallback=True) as rd:
    player = rd.get_player(1970288503)
```

## Errors and contributions

All package exceptions inherit from `RivalsAPIError` (also exported under the
legacy `RivalsDataError` name). See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, code layout, change workflow, and
notes for new contributors. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
is the handoff document for new coding sessions.

This project is not affiliated with RivalsData, RivalsTracker, Tracker.gg,
NetEase, or Marvel. Keep
request rates reasonable and respect the site's terms.

## Multi-provider data

Existing functions combine public RivalsData, RivalsTracker, and Tracker.gg data with evidence-based selection of comparable values. New functions expose rank timelines, cosmetics, encounters, advanced career stats, global analytics, and community listings. Live Custom-game detection is not currently supported by the investigated public sources. See [provider integration](docs/PROVIDER_INTEGRATION.md) for examples, source semantics, and browser setup. Use `RivalsClient(enrich=False)` for RivalsData-only behavior.

## Documentation

- [Release notes and migration guide](docs/CHANGELOG.md)
- [Provider integration and data-selection rules](docs/PROVIDER_INTEGRATION.md)
- [Research findings and unsupported features](docs/PROVIDER_FEATURE_GAPS.md)
- [RivalsTracker API audit](docs/RIVALSTRACKER_API_AUDIT.md)
- [Tracker.gg API audit](docs/TRACKER_NETWORK_API.md)
- [Observed RivalsData endpoints](docs/API.md)
