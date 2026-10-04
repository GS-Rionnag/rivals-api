# Project context

## Goal and boundaries

`rivals-api` is an unofficial Python client and read-only tracker that combines
public Marvel Rivals data from RivalsData, RivalsTracker, and Tracker.gg. It
provides typed, mapping-compatible responses, provider-specific analytics, a
Python API, and an MCP server. It is not affiliated with those providers,
NetEase, or Marvel.

Only public read routes are in scope. Do not add account edits, private-profile
access, community posting/voting, or refresh queue actions. Live Custom-game
discovery has not been verified from the supported providers and is not an
implemented feature. Provider APIs are unofficial/undocumented and may change.

## Current package

- Distribution: `rivals-api`; preferred import: `rivals_api`.
- Compatibility: `rivalsdata` and `RivalsDataClient` remain aliases.
- Version: `5.3.0`.
- Python `>=3.10`, Hatchling build, `src/` layout.
- Runtime HTTP dependency: `curl-cffi`; optional browser fallback: Camoufox.
- Public entry point: `RivalsClient`.
- GitHub: <https://github.com/GS-Rionnag/rivals-api>.

## Code map

- `src/rivals_api/client.py`: primary client, player lookup, source enrichment,
  provider selection and client-wide resource managers.
- `src/rivals_api/providers.py`: independent provider transports, response
  handling, caching, browser reuse, privacy and rate-limit errors.
- `src/rivals_api/normalize.py` and `selection.py`: provider adapters,
  comparable-scope checks, source evidence and selected-value metadata.
- `src/rivals_api/attribution.py`: canonical longest-played-hero match attribution,
  class grouping, shared calculation caching and explicit unresolved coverage.
- `src/rivals_api/history.py`: paginated history federation, source cursors,
  deduplication and consistent filtering.
- `src/rivals_api/resources.py` and `extensions.py`: player/site resources,
  added analytics and community reads.
- `src/rivals_api/models.py`: tolerant mapping/attribute models and typed rows.
- `src/rivals_api/mcp_server.py`: read-only MCP tools, dashboard UI and ASGI app.
- `src/rivalsdata/`: compatibility import shims.
- `docs/PROVIDER_INTEGRATION.md`: supported source behavior and selection rules.
- `docs/PROVIDER_FEATURE_GAPS.md`: feature comparison and known gaps.
- `docs/CHANGELOG.md`: release notes and 2.0 migration steps.

## Provider and selection behavior

`RivalsClient(enrich=True)` uses RivalsData for its established endpoints and
enriches results where public RivalsTracker or Tracker.gg data can be compared.
It preserves the old RivalsData-only request behavior with `enrich=False`.
Provider-specific analytics remain separately callable. Optional Camoufox
support is enabled with `use_browser_fallback=True`.

Every merged value carries source evidence. Comparisons respect player, match,
season, mode, unit and count-basis scope. Invalid values are excluded; complete
match details can outrank summaries; verified newer updates or agreement among
distinct sources can resolve conflicts. Unresolved conflicts remain visible.
Counts are selected as a group and derived totals/rates follow that selected
population. Read `docs/PROVIDER_INTEGRATION.md` before changing merge behavior.

## Public interface

`client.get_player(uid_or_name)` returns a mapping-compatible `Player`; raw
response fields remain accessible. Player sections include match history,
live-game data, heroes, maps, hero bans, rank history, encounters, cosmetics,
proficiency, punishment and name history. Client-wide resources include match
details, leaderboards, heroes, team-ups, insights, factions, profiles and
favorites. New analytics and public community resources are documented in
`docs/PROVIDER_INTEGRATION.md` and the feature-gap inventory.

History rows carry their originating client and expose `match.get_details()`.
Both bounded/all fetches and iteration return these bound `Match` objects. The
method returns a new typed full `Match` through `client.matches.get(...)`, with
`refresh=True` available to bypass detail/provider caches. The client reference
is excluded from model serialization. Keep it open while fetching details.
The shared fetcher in `match_details.py` validates provider match IDs, preserves
raw responses and errors, merges roster/hero records by identity, and exposes
per-field source decisions and completeness. Ambiguous player bridges remain
unmatched. Accuracy percent is distinct from session hit rate; raw RD hero
accuracy retains ratio units. Detail caches are scoped to the enrichment setting;
partial cached evidence remains usable for request-free calculations but is
retried by detail lookups.

Match models resolve map, queue, gameplay, platform, rank, season, and hero
references offline from packaged provider catalogs. References format as names
and expose `.id`; the original numeric fields remain except `match.platform`,
which is a typed Platform with `.platform_id` providing the previous scalar.
Gameplay labels come from the map/objective context rather than guessing a
global interpretation of `game_play_mode_id`. Unknown codes stay explicit.
The catalog covers 118 map variants and 20 observed seasons; source evidence
and serialization/migration details are in `docs/GAME_REFERENCES.md`.

The MCP server exposes read-only tools over stdio or Streamable HTTP. It does
not implement authentication; remote deployments must supply an authenticated
gateway. The dashboard shows a snapshot and performs provider requests when a
tool runs.

MCP `search_players(name)` returns a list of RivalsTracker candidates with names
and numeric game UIDs. `get_player_profile(uid)` retrieves the chosen profile
by positive integer UID, including its current-season competitive win rate.
`search_player_candidates` is an alias for the list search; the existing
`get_player(uid_or_name)` tool remains available. The search tool previously
resolved one account, so callers must migrate to handling list results.

## Development and release

Create an isolated virtual environment and install `.[dev]`. Install
`.[browser,dev]` only when working on Camoufox. Tests use recorded fixtures and
mock transports; avoid network-dependent checks in the normal test suite.
Builds publish to PyPI when a GitHub release is published. Update the package
version in `pyproject.toml` and `src/rivals_api/__init__.py` together, maintain
the workflow's PyPI project URL and credentials, and document user-visible
changes in `docs/CHANGELOG.md`.

Follow [RELEASING.md](RELEASING.md) for future releases. The chat chooses the
smallest appropriate bump automatically: patch for compatible fixes, minor for
compatible features, and major only for necessary public API incompatibility.
Prefer incremental changes and compatible migrations. A push alone does not
imply a package release; documentation-only changes normally need no bump.

Research docs identify observed behavior separately from inferences. Preserve
these uncertainties, source labels, and privacy boundaries when extending the
client.

Overall/hero/class requests default to the current season and mode="all"
(Competitive plus Quickplay; Custom/Arcade excluded). They also accept
season="current", a positive provider season ID, or season="all".
Current-season detection normalizes Tracker numeric string IDs and falls back
to the live RivalsTracker global /heroes/stats season; it never substitutes
all-seasons data or the player's last played season for an unverifiable current season.
Overall, hero, and class win-rate functions default to `method="normal"`:
scoped provider summaries without match history or detail requests. One shared
summary calculation retains source, count basis, disagreements and missing
coverage. Overall counts prefer direct career records, then map totals, then
uncertain rank battles. Hero/class participation can differ from unique matches.
`method="precise"` traverses available history and verifies completed outcomes;
hero/class rates use longest-played attribution with unresolved cases reported.
All applicable MCP tools expose the same method argument.

`cache.py` persists history and details in SQLite, scoped by UID/season/enrichment
for history and match/enrichment for details. Each provider independently stops
newest-page traversal at a cached match only after a completed chronological
scan. Failed or unordered scans cannot establish new boundaries. Retained tails
are merged with fresh rows; missing details retry. `cache_dir`,
`RIVALS_API_CACHE_DIR`, and `persist_cache=False` configure storage. This assumes
no older-history backfill behind a retained boundary. Calculation caches remain
short lived. See README and the integration guide for usage.
The legacy profile win_rate remains a competitive snapshot.
