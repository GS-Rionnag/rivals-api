# rivalsdata-api

An unofficial Python client for RivalsData's public Marvel Rivals data. It
uses the site's undocumented API, so routes and fields can change. The client
keeps unknown response fields accessible instead of discarding them.

## Install

Python 3.10 or newer:

```console
python -m pip install rivalsdata-api
```

For editable development, clone the repository and run
`python -m pip install -e '.[dev]'`. The optional Camoufox Cloudflare fallback
is installed with `python -m pip install 'rivalsdata-api[browser]'`, followed
by `python -m camoufox fetch`.

## Quick start

```python
from rivalsdata import RivalsDataClient, hero_id, hero_name

print(hero_name(1016))  # Loki
print(hero_id("Loki"))  # 1016

with RivalsDataClient() as rd:
    player = rd.get_player("GS-")  # numeric UID works too
    print(player.name, player.level, player.rank_game_season)

    # Player profile sections are lazy resource managers.
    hero_season = player.heroes.fetch(season=20)
    all_hero_seasons = player.heroes.fetch(season="all")
    map_stats = player.stats.maps(season=20)
    match_page = player.matches.fetch(season=20)

    # Current match (None if the profile is not currently in a game).
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

## MCP server (ChatGPT and Claude)

Install the MCP extra and the package:

```console
python -m pip install 'rivalsdata-api[mcp]'
```

The server exposes read-only tools for player search and profiles, a player's
current live match (when they are in one), match history, player stats,
leaderboards, heroes, team-ups, public insights, matches, and factions. The
`show_player_dashboard` tool returns an MCP-UI player card with rank and
competitive record plus one optional data section per call: current match
roster, hero win-rate chart, or recent match form with K/D/A. This keeps each
dashboard pull to the profile plus at most one additional endpoint. It supports
local stdio for Claude Desktop
and Streamable HTTP for remote MCP clients such as ChatGPT. Data comes from
RivalsData's undocumented API and may change; profile match history can be
private.

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
    "rivalsdata": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "rivalsdata.mcp_server"]
    }
  }
}
```

On macOS/Linux, use the environment's `bin/python` path. Restart Claude Desktop
after saving the configuration.

### ChatGPT or remote Claude connector

Run the server on a host reachable over HTTPS:

```console
uvicorn rivalsdata.mcp_server:app --host 0.0.0.0 --port 8000
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
with RivalsDataClient() as rd:
    player = rd.get_player(1970288503)             # Player
    proficiency = player.proficiency.fetch()       # ProficiencyResponse
    account = next(iter(proficiency.accounts.values()))  # Proficiency
    hero = account.hero_proficiency_infos["1011"]   # HeroProficiency
    print(hero.proficiency_level, hero.proficiency_point)

    tier_list = rd.heroes.tier_list()               # TierListResponse
    print(tier_list.heroes[0].hero_id)             # Character
```

## Public resources

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
with RivalsDataClient(use_browser_fallback=True) as rd:
    player = rd.get_player(1970288503)
```

## Errors and contributions

All package exceptions inherit from `RivalsDataError`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, code layout, change workflow, and
notes for new contributors. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
is the handoff document for new coding sessions.

This project is not affiliated with RivalsData, NetEase, or Marvel. Keep
request rates reasonable and respect the site's terms.
