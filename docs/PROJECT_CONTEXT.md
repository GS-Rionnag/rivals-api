# Project context for new chats and contributors

## Goal and boundaries

`rivalsdata-api` is an unofficial Python wrapper around public RivalsData pages
and their undocumented JSON API. It should offer ergonomic, discord.py-like
objects while retaining unknown JSON keys so the wrapper remains useful as the
site evolves. It is not affiliated with RivalsData, NetEase, or Marvel.

Prefer read-only endpoints needed by public pages. Some frontend routes concern
profile editing, favorites, account binding, and private profiles; the UI
requests for these have not been fully characterized and should not be treated
as public, stable methods. Keep requests respectful and conservative.

## Current package

- Distribution: `rivalsdata-api`; import: `rivalsdata`.
- Version: `1.2.3`.
- Python `>=3.10`, Hatchling build, `src/` layout.
- Runtime HTTP dependency: `curl-cffi`; optional browser fallback: Camoufox.
- Public entry point: `RivalsDataClient`.
- GitHub: <https://github.com/GS-Rionnag/rivalsdata-api>.

## Code map

- `src/rivalsdata/client.py`: HTTP session, search, player lookup, HTTP errors,
  TLS impersonation and optional Camoufox GET/POST fallback.
- `src/rivalsdata/models.py`: tolerant mapping/attribute models, `Player`, and
  integer win-rate convenience properties.
- `src/rivalsdata/resources.py`: managers for player sections and global
  leaderboards, heroes, team-ups, insights, factions, and matches.
- `src/rivalsdata/exceptions.py`: public exception hierarchy.
- `src/rivalsdata/__init__.py`: public exports/version.
- `docs/API.md`: UI routes, observed endpoints, request arguments, sampled
  response fields, and explicit uncertainties.
- `CONTRIBUTING.md`: development and contribution workflow.

## Object interface

`client.get_player(uid_or_name)` returns a mapping-compatible `Player`.
Profile fields support `player.name`, `player.level`, and `player["level"]`.
Nested JSON is recursively attribute-accessible. `player.raw` retains a shallow
copy of the full response.

Lazy subresources include `player.heroes.fetch(...)`, `player.matches.fetch(...)`,
`player.teammates.fetch(...)`, `player.crosshairs.fetch()`,
`player.proficiency.fetch()`, `player.punishments.fetch()`,
`player.name_history.fetch()`, and `player.stats.heroes/maps/bans/classes(...)`.
Client-wide resources include `client.leaderboards`, `client.heroes`,
`client.team_ups`, `client.insights`, `client.factions`, and `client.matches`.
`client.profiles` and `client.favorites` have typed read methods. The profile
endpoint takes a numeric UID; the wrapper can resolve a username first.
Favorites requires numeric UIDs and returns player summary rows.
Rows offer `.win_rate` and `.winrate` integer-percent access when data supports
it; all original data remains in mapping access.

The player overview's overall win rate (`player.win_rate`) is for the current
competitive season (latest available season with usable counts when there is no
direct source rate), not an all-seasons aggregate. Keep this scope explicit in
docs, MCP descriptions, and dashboard labels. Hero/class stats have separate
season selectors.

`player.stats.classes(season=...)` groups observed hero IDs into tank, support,
and DPS. Supply a numeric season ID for one season or `season="all"` for
combined all-seasons stats; the latter sends `season=-1` to the upstream API.
The detailed `player.stats.heroes` method and MCP stats tool accept the same
selector. Omitting the season keeps the endpoint default.
It sums games, wins, losses, and available MVP/SVP counts separately
for competitive and quickplay, with win rates calculated from summed wins and
losses. The response has typed `classes` rows and an `excluded` list for unknown
roles or incomplete win/loss data. MCP exposes it through `get_player_stats`
with `category="classes"`. Response `metadata` describes the source, formula,
season scope, and limitations. Upstream hero-switch attribution and distinct
match counts are unverified; do not derive player overall win rate from class
totals. All-seasons coverage is limited to returned records, with complete
lifetime coverage unverified. Excluded rows produce a metadata warning.
Role IDs and the corrected Angela/Daredevil IDs were
verified against RivalsData's roster on 2026-09-30; Deadpool has separate role
variants (10571/10572/10573), while generic 1057 remains unclassified.

Camoufox inspection found no cumulative hero hours in current-season or
all-seasons player stats. Match hero usage does include `play_time` in seconds.
See `docs/API.md` for the recorded investigation; no playtime aggregation
method was added.

## Observed API details

The major UI areas inspected are home, player profile/tabs, global leaderboard,
hero tier list and hero detail tabs, team-ups, insights, factions, and match
detail pages. Main public request families are:

- `POST /players/search`, `POST /player`.
- `POST /player/heroes`, `/crosshairs`, `/matches[/cached]`, `/teammates`,
  `/proficiency`, `/stats/heroes`, `/stats/maps`, `/stats/bans`, `/punishments`,
  `/name-history`.
- `GET /leaderboards`, `/stats/tierlist`, `/stats/teamups`, `/stats/heroes/{id}`,
  `/stats/meta/{id}`, `/stats/leaderboards`, `/stats/punishments`, `/stats/xp`,
  `/stats/oaa`, `/stats/commbans`, `/stats/leavers`, and `/faction/{id}`.
- `POST /match` with `{"match_id": "..."}`. Verified against a real match link
  opened from the public GS- profile. The returned object contains replay id,
  mode/map/time, draft picks/bans, both teams, players' combat stats, and hero
  usage.
- `GET /profiles/{uid}` returns profile social metadata and `POST /favorites`
  returns public player summaries. Both were checked through the browser.

The hero detail Counters and Synergy tabs showed “Coming Soon” on inspection.
The Live Game tab did not expose data for the sampled player. Do not invent
endpoints for these. Match history may be private; the public UI has a separate
cached route. Match page and response samples are in `docs/API.md`.

Frontend asset strings mention `/profiles`, profile edit, `/bind/start`, and
`/bind/check`, but their full contract/auth behavior isn't verified. Edit/bind
endpoints can change account state and are intentionally not implemented by
this read-only package yet. `client.matches.get` uses the verified `match_id`
payload.

The hero meta endpoint requires `range=30d`, `90d`, or `180d`; bare integers
are rejected. The website currently shows Season 10 / season value 20 and OS `1` for PC on
the inspected UI. Treat those as site values, not permanent constants.

## Contributor workflow

Before a change, read `CONTRIBUTING.md`, `docs/API.md`, and the relevant source.
For a new endpoint, capture it from a visible UI action or a read-only browser
request, record its method/path/parameters and sample response in `docs/API.md`,
then implement it through the shared client request helpers. Favor a typed
resource wrapper plus generic `DataModel` over brittle assumptions about every
field. Keep models mapping-compatible.

Use a virtual environment. Install editable dependencies with
`python -m pip install -e '.[dev]'`; use `'[browser,dev]'` only for browser
fallback work. The global host Python has unrelated package conflicts; don't
change global dependencies to resolve those.

Mocked tests in `tests/` cover hero lookups, typed responses, and calculated
class stats. Keep network-dependent checks opt-in. Run pytest, Ruff, and package
builds for code checks. Commit coherent
milestones and push to `origin` when explicitly requested by the project owner.
