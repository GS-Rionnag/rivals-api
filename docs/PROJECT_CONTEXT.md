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
- Version: `4.0.0`.
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

Research docs identify observed behavior separately from inferences. Preserve
these uncertainties, source labels, and privacy boundaries when extending the
client.

Overall/hero/class requests default to the current season and mode="all"
(Competitive plus Quickplay; Custom/Arcade excluded). Hero/class stats use match attribution.
Every match counts once for its longest-played hero. Missing playtime, ties and
conflicts remain unresolved, with coverage metadata. Provider summaries are
separately named `summary_heroes`, `summary_classes`, and `heroes.summary`.
Hero/class MCP tools no longer expose calculation methods; list tools return
`data` plus metadata. See the integration guide for migration details.

`player.stats.win_rate()` selects scoped RT/Tracker career records as intact
counts and checks them against history. RD rank battle records remain ineligible
diagnostics. Missing summaries fall back to known tracked outcomes. Metadata
preserves uncertainty and coverage; no percentage averaging or full-coverage
claim. The MCP overall tool no longer exposes method, cached, hero or teammate.
The legacy profile win_rate property remains a competitive snapshot; normal
season requests and matches.fetch_win_rate() use the new canonical calculation.
