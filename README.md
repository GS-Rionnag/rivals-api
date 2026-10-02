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
    print(player.win_rate)  # Current-season competitive win rate

    # Player profile sections are lazy resource managers.
    hero_season = player.heroes.fetch(season=20)
    all_hero_seasons = player.heroes.fetch(season="all")
    map_stats = player.stats.maps(season=20)
    match_page = player.matches.fetch(season=20)

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

The player overview's overall win rate (`player.win_rate`) is the **current-season
competitive win rate**. It uses the latest available competitive season with
usable counts when a direct source rate is absent; it does not combine seasons.
Hero and class stats use the season selector supplied to their own methods.

Calculated player class statistics are available through
`player.stats.classes(season=20)` and the MCP `get_player_stats` tool with
`category="classes"`. Pass a numeric season ID for that season, or
`season="all"` for combined all-seasons data, matching `player.heroes.fetch`.
Omitting the season uses the endpoint default. `player.stats.heroes` also
accepts `season="all"`. Each row contains `player_class` (`tank`, `support`,
`dps`), the official role, hero IDs, and separate `competitive` and `quickplay`
totals for games, wins, losses, and available MVP/SVP counts.

```python
with RivalsClient() as rd:
    player = rd.get_player("GS-")
    stats = player.stats.classes(season=20)
    all_seasons = player.stats.classes(season="all")
    for row in stats.classes:
        print(row.player_class, row.competitive.win_rate)
    print(stats.excluded)  # Unknown roles or incomplete win/loss records
```

For MCP, use `get_player_stats(uid_or_name="GS-", category="classes", season=20)`
for one season, or `season="all"` for combined all-seasons stats. Both return
the same class response structure.

Detailed hero stats require a mode and match the website's selected tab:

```python
competitive = player.stats.heroes(mode="competitive", season="all")
quickplay = player.stats.heroes(mode="quickplay", season=20)
print(competitive[0].competitive.games)
print(competitive[0].rank)  # Hero leaderboard position, or None if unavailable
```

Only heroes with data for the chosen mode are returned, with that mode's nested
stats and a `mode` label; the other mode is omitted. Rows are sorted by the
selected mode's games played descending, with ties retaining the JSON order.
The source returns both modes in one response; filtering and sorting happen
in this package, as they do on the website. Existing calls to
`player.stats.heroes()` must now supply `mode`. MCP also requires `mode` when
`get_player_stats` uses `category="heroes"`; other categories do not require it.
The separate summary method `player.heroes.fetch()` keeps its existing behavior.

Hero stats include the source's top-level `rank`, matching the **#N** displayed
in the left-hand hero card. It is preserved for either mode and all-seasons
requests when supplied by the source; it is not recalculated as a quickplay or
all-seasons leaderboard position. Missing ranks are returned as `None`.

Win rates are `total wins / (total wins + total losses)`, rounded to an integer
percent. They are weighted by hero records, rather than averaging hero win
rates. The response's `metadata` identifies the source, formula, and requested
season scope. Upstream hero-switch attribution is unknown; hero records may
overlap within a match, so these totals cannot establish distinct match counts
or the player's overall match win rate. All-seasons coverage is limited to
records returned by the source; complete lifetime coverage is unverified.
Excluded rows also produce a metadata warning. Empty modes
have a `None` win rate. Role mappings were observed on RivalsData on
2026-09-30, including Deadpool's separate role IDs; generic Deadpool and unknown
IDs are excluded rather than assigned a guessed class.

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
`player.matches.fetch()` returns a `MatchHistory`, and
`player.proficiency.fetch()` returns a `ProficiencyResponse`. Nested match
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

- [2.0.0 release notes and migration guide](docs/CHANGELOG.md)
- [Provider integration and data-selection rules](docs/PROVIDER_INTEGRATION.md)
- [Research findings and unsupported features](docs/PROVIDER_FEATURE_GAPS.md)
- [RivalsTracker API audit](docs/RIVALSTRACKER_API_AUDIT.md)
- [Tracker.gg API audit](docs/TRACKER_NETWORK_API.md)
- [Observed RivalsData endpoints](docs/API.md)
