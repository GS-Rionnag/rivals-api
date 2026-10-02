# Changelog

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
