# Changelog

## 4.0.0 — 2026-10-03

This release changes canonical hero/class statistics from provider participation
summaries to longest-played-hero match attribution. All canonical win-rate APIs
now default to Competitive plus Quickplay (`mode="all"`). MCP hero/class list
results and win-rate schemas have changed; see the migration notes below.

### Migration

- Use `player.stats.win_rate(season=..., mode=...)` for the season calculation.
  The profile `player.win_rate` property remains a competitive snapshot.
- Hero/class requests now count deduplicated matches once per longest-played
  hero, with explicit unresolved coverage. Provider summaries moved to
  `summary_heroes`, `summary_classes`, and `player.heroes.summary`.
- Supply `mode="competitive"` to retain the previous canonical default scope;
  `mode="all"` combines Competitive and Quickplay and excludes other queues.
- MCP hero lists now return `data` plus `metadata`. Overall/hero/class win-rate
  tools no longer accept `method`; overall tools also drop `cached`, `hero`, and
  `teammate`. Python legacy method overrides remain available.

### Changes

- Added `player.stats.win_rate()` and simplified MCP overall win-rate requests:
  intact season career records are selected per mode and checked against history,
  with explicit disagreements and partial-history fallbacks instead of averaging.
- Overall, hero, and class canonical rates now accept competitive/quickplay/all
  and default to all (Competitive plus Quickplay, excluding Custom/Arcade).

- Include Tracker.gg in combined match history, with verified player identity,
  resumable pagination, deduplication, and explicit season coverage limitations.
- Correct the GS-4 comparison: an empty provider history does not establish
  absence of competitive activity. Tracker.gg exposes competitive matches
  missing from RivalsData's cached history; RivalsTracker's API also returned
  competitive matches in the 2026-10-03 check.

- Hero/class requests now count each match once for its longest-played hero.
  Missing playtime, ties, identity ambiguity and source conflicts stay unresolved.
- Normal hero/class requests default to the current season, with automatic
  caching and explicit coverage. Their MCP schemas no longer expose `method`.
- Provider hero/class summaries moved to explicitly named summary methods; empty
  RivalsData competitive rows can now fall back to Tracker summary rows.


## 3.0.0 — 2026-10-02

This release changes `match.platform` from a scalar to a typed `Platform`.
Use `match.platform.id` or `match.platform_id` for the previous numeric value.
Serialized matches now contain a structured `platform` and readable reference
objects alongside legacy numeric fields. See `docs/GAME_REFERENCES.md` for
migration details.

- Added readable typed map, queue, gameplay, platform, rank, season, and hero
  references to match/history models, including nested participants and draft
  entries. Names resolve offline; unknown IDs remain explicit. Map 1288 now
  formats as Hell's Heaven, with its Hydra Charteris Base location accessible.
  `match.platform` is now a Platform object; use `.platform_id` for its scalar.
  Serialized responses include structured reference objects alongside legacy IDs.
- Lazy details retain missing same-match context from their originating history
  row, with sources recorded in `provider_metadata.history_context`.
- Added lazy `Match.get_details(refresh=False)` to typed history rows from both
  providers, bounded/all fetches, and iteration. It returns a new typed full
  match through the same combined fetcher as `client.matches.get(...)`.
- Match details preserve raw provider responses, failures, completeness,
  per-field provenance, and unresolved conflicts. They add provider-only roster
  entries and hero segments while retaining ambiguous identities separately;
  responses for a different match are rejected.
- Separated `session_hit_rate` from accuracy. Added `accuracy_percent` for
  player/hero percentage access, preserving RD's legacy player-percentage and
  hero-ratio `accuracy` fields. Unusable accuracy is missing.
- Scoped shared detail caches by enrichment mode and isolated returned objects.
  Partial details retry on lookup; `refresh=True` bypasses both detail and
  provider response caches. MCP `get_match` also accepts `refresh`.

## 2.1.0 — 2026-10-02

- `player.matches.fetch` now requires `limit`: pass a positive integer for a
  bounded, resumable page of combined history, or `"all"` to traverse all
  available pages. Results are merged and deduplicated across providers.
- Added overall, hero, and class win-rate methods to Python and MCP. Each
  defaults to a quick provider-summary estimate and also supports exact
  calculations over match history or request-free calculations from full
  history already cached in the current Python process. Hero/class exact rates
  attribute matches using the player's longest-played hero from match details,
  with a summary-hero fallback when detail evidence is unavailable.
- Match history is shared in a bounded process-level calculation cache so
  separate client instances can reuse previously fetched full history. Results
  expose provider coverage, unknown outcomes, and hero attribution fallbacks;
  exact hero/class calls may require a detail lookup for each match.
- MCP `search_players(name)` now returns a list of matching players with names
  and numeric game UIDs instead of automatically resolving one account. Callers
  must handle list results, including an empty list for no matches.
- Added MCP `get_player_profile(uid)` to fetch the selected player's overview by
  numeric UID. `get_player(uid_or_name)` remains available, and
  `search_player_candidates` is an alias for the list search.

## 2.0.0 — 2026-10-02

This release changes the project from a RivalsData-only wrapper into **rivals-api**,
a multi-source Marvel Rivals stats client and read-only tracker. RivalsData,
RivalsTracker, and Tracker.gg are used where their public data overlaps; provider
specific endpoints remain available when their data does not overlap.

### Package and migration

- PyPI distribution: `rivals-api` (previously `rivalsdata-api`).
- Preferred import: `rivals_api` (previously `rivalsdata`).
- Preferred client: `RivalsClient` (previously `RivalsDataClient`).
- `RivalsDataClient`, `RivalsDataError`, and `RivalsDataHTTPError` remain exported
  aliases. The `rivalsdata` module path also forwards imports to `rivals_api`.
- To avoid two installed distributions owning the same compatibility files,
  remove the old distribution before installing the renamed one:

  ```console
  python -m pip uninstall rivalsdata-api
  python -m pip install rivals-api
  ```

  Install optional features with `rivals-api[browser]` or `rivals-api[mcp]`.

### Provider integration and data selection

- Existing player, match, hero, rank, and live-game methods can enrich RivalsData
  results with public RivalsTracker and Tracker.gg data. Set `enrich=False` for
  the original RivalsData-only request behavior.
- Provider requests use separate transports and caches. The optional Camoufox
  fallback supports sites that reject a normal HTTP session. Provider failures,
  privacy limits, freshness and source coverage remain visible to callers.
- Comparable values are selected using validity, player/match/season/mode scope,
  units, verified update times, completed-detail coverage, and agreement between
  distinct providers. Original alternatives and selection explanations remain
  in `provider_metadata`.
- Match counts, wins and losses are selected together. Derived win rates,
  averages and totals follow the selected match population instead of mixing
  incompatible samples. Rank-system match counts and separately reported career
  counts are preserved as different measures.
- Match history can combine provider pages, preserve opaque per-source cursors,
  deduplicate match IDs, and apply filters consistently. Match details are
  joined by player/hero identity and rejected when the match IDs disagree.
- Tracker.gg time fields are normalized only when their display metadata states
  the unit. Damage taken is not silently relabeled as damage blocked.

### Expanded client features

- Added provider-specific rank timelines, cosmetics, player encounters, richer
  career and hero analytics, global rank/leaderboard analytics, and public
  community listings.
- Added a packaged, dated 56-hero reference catalog, hero name/ID resolution,
  and names on typed player and match data.
- Expanded the read-only MCP server with player dashboards, match and hero
  analytics, rank-history and community tools. It supports local stdio and
  Streamable HTTP deployments.
- Added provider comparisons, API audits, captured fixtures, and documented
  data-quality limitations in `docs/`.

### Scope and known gaps

- These sources are community/third-party or undocumented APIs and may change;
  profiles can be private, old, incomplete, or disagree on field definitions.
- Live Custom-game discovery is not implemented. Existing live match methods
  only return matches exposed by their current providers; a source listing past
  Custom matches does not establish a live Custom feed.
- Custom game history may be available on some tracker profiles, but coverage
  varies by player and provider. The source research and examples are linked in
  `docs/PROVIDER_FEATURE_GAPS.md` and `docs/PROVIDER_INTEGRATION.md`.
- The package is read-only. It does not edit player accounts, post community
  listings, vote on community content, or access private profile data.

## Earlier releases

See the [GitHub release history](https://github.com/GS-Rionnag/rivals-api/releases)
for versions published under the former `rivalsdata-api` project name.
