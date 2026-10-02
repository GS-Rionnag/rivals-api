# Multi-provider integration

The client now combines RivalsData, RivalsTracker and Tracker.gg public reads. Existing method names, required arguments, typed Mapping responses and primary fields remain supported. No account mutations, refresh queue requests, voting, posting or messaging are performed.

```python
from rivals_api import RivalsClient

with RivalsClient(use_browser_fallback=True) as client:
    player = client.get_player(691218686)
    page = player.matches.fetch(mode="custom", season=20, cached=False)
    match = client.matches.get(page.matches[0].match_uid)
    for team in match.teams:
        for participant in team.players:
            print(participant.name, participant.get("heroes"))
    print(player.analytics.rank_history(season=20).data)
```

## Compatibility and source policy

- `enrich=True` is the default. Set `enrich=False` for the original RivalsData-only calls/results. New provider-specific methods remain callable regardless of this automatic enrichment setting.
- Conflicting values are selected automatically using validity, matching scope/units, completed-detail evidence, genuine update times and cross-provider agreement. A tie keeps the current value and is marked uncertain. `provider_metadata.selections` explains each choice; observations and conflicts preserve the alternatives. Wins/losses/games are selected as a group, never summed across providers. Derived rates are recomputed when that group changes; unavailable old-population averages become null. Provider outages cannot erase a successful primary match/profile/history result.
- RivalsTracker is the first fallback for profiles/history, especially Custom history. Full matches add RivalsTracker hero K/D/A and Tracker hero combat segments. Tracker adds advanced stats plus raw/display/percentile metadata. `provider_errors` on the client records optional enrichment failures.
- Original RD lifetime hero/class selectors remain supported. Their records are not enriched from undocumented RT lifetime selectors or Tracker's current-season default. `career(season="all")` explicitly enumerates the Tracker season catalog and returns separate season segments.
- Global rank/platform buckets differ. Additional tier-list/team-up/leaderboard data is stored separately with its scope; existing filtered aggregates are preserved.
- History's `next_cursor` is opaque and must be reused with the same UID, season, mode, hero, teammate and cached setting. Federation uses both providers' pagination and deduplicates across pages. Ordering is descending within each returned page; cross-provider pagination does not establish globally sorted page boundaries. Use `player.matches.iter(...)` to exhaust the history, including empty continuation pages. Numeric modes and quickplay/competitive/custom names resolve to IDs 1/2/3.
- RivalsTracker cannot apply a teammate filter. Such requests retain RD filtering and explicitly report that the alternative provider was skipped. Explicit season/mode/hero filters are checked on all rows, including uncached responses that ignore upstream selectors. Uncached teammate filtering verifies same-team membership from full match detail; this costs additional reads.
- Tracker hero participation counts may be fractional. Raw stat keys/display labels are retained. `totalDamageTaken` is never silently relabeled as the client's `blocked` statistic; RT's opaque `last_kill` is preserved under its source key.
- Provider sessions/caches are independent and close with the client. Cache is bounded (128 entries per provider), configurable with `provider_cache_ttl`, and returns defensive copies. Browser contexts are reused during a client lifetime and close on exit. Use the synchronous client on the thread that created its browser context.

## Existing functions with additions

| Function | Addition |
|---|---|
| `client.get_player(...)` | RT fallback, section visibility and missing profile fields |
| `player.matches.fetch(...)` | Combined history, Custom coverage, resumable deduplication and source errors |
| `client.matches.get(...)` | Per-hero match K/D/A, advanced combat/hero segments and completeness flags |
| `player.stats.heroes(...)` | Cumulative RT combat/playtime and Tracker advanced stat metadata; original mode filtering and ordering remain |
| `player.stats.classes(...)` | Additional cumulative combat/playtime totals where all contributing rows have data |
| `player.teammates.fetch(...)` | Last encounter and encounter/season metadata from Tracker |
| `player.name_history.fetch()` | First/last detection, usage counts and current-name metadata |
| `client.heroes.get(...)` | Dated reference catalog including abilities/passives |
| `client.heroes.meta(...)` | Separately scoped daily combat history |
| `client.heroes.tier_list(...)` | Additional global hero/map/mirror/ban metadata, separately scoped |
| `client.heroes.leaderboard(...)` | Alternative hero-player metrics, separately scoped |
| `client.team_ups.fetch(...)` | Additional team-up pair variants by provider rank bucket |

## New Python functions

Each new analytics function returns an attribute-accessible Mapping envelope `{data, source, scope}`. Raw provider fields are retained, including opaque fields whose meanings are not established.

| Function | Purpose |
|---|---|
| `client.search_players(name)` | Multiple search candidates with numeric UID |
| `player.analytics.rank_history(season=...)` | Rank timeline, match transitions and summary |
| `player.analytics.rank_stats(season=...)` | Tracker rank-stat history |
| `player.analytics.cosmetics()` | Observed skins, usage/performance/dates and name changes |
| `player.punishments.history()` | Historical punishment records |
| `player.name_history.events()` | Match-linked name changes |
| `player.stats.career(season=..., mode=...)` | Detailed overview/hero/role/rank-peak segments |
| `player.stats.matchups(season=...)` | Personal enemy-hero results |
| `player.analytics.encounters(season=..., mode=..., local_offset=...)` | Teammates and enemies; `local_offset` uses JS timezone-offset minutes |
| `player.teammates.encounters(...)` | Alias for encounters |
| `player.analytics.seasons()` | Named season catalog/default/current IDs |
| `client.heroes.reference(hero_id)` | Dated packaged hero/ability/form/team-up catalog |
| `client.heroes.matchups(hero_id)` | Global enemy-hero matrix |
| `client.heroes.history(hero_id, days=..., platform=...)` | Daily combat/meta trends, fixed Celestial+ scope |
| `client.heroes.season_stats(season=...)` | Global hero/map/ban/mirror/team-up rank buckets |
| `client.team_ups.compositions()` | Team role-composition stats |
| `client.analytics.rank_distribution()` | Tracked-population counts and percentages |
| `client.analytics.skin_popularity()` | Global observed skin usage |
| `client.analytics.hero_players(hero_id, season=..., device=...)` | Alternative hero leaderboard |
| `client.community.crosshairs(...)` | Gallery, search, sort, pagination and profile crosshairs |
| `client.community.looking_for_group(**filters)` | Public LFG listings |

The other methods on `player.analytics` and `client.analytics` are the underlying equivalents of these resource methods.

## MCP

43 read-only tools are registered. They cover the new functions and the previously Python-only crosshairs, proficiency, punishments, name history, hero leaderboard, public profile and favorites. `get_player_matches` now accepts `cached=False` and mode names.

Use `search_players(name="silo")` to get a list of matching accounts, with each
candidate's name and numeric game UID. Select an account, then call
`get_player_profile(uid=283622404)` for its overview, including available rank,
level and current-season competitive win rate. Search preserves provider fields
and special characters in names. `search_player_candidates` remains an alias
for the list search; `get_player(uid_or_name=...)` remains available for callers
that already have a UID or an exact name. MCP `search_players` previously
returned one resolved account; callers must now handle a list, including an
empty list when no candidates are returned.

MCP enables browser fallback by default when Camoufox is available. Set
`RIVALS_API_BROWSER_FALLBACK=false` to disable browser launches. The former
`RIVALSDATA_BROWSER_FALLBACK` variable remains a fallback alias. Install the
browser extra and fetch its binary to use Tracker through Cloudflare:

```text
pip install 'rivals-api[browser,mcp]'
python -m camoufox fetch
```

## Boundaries and verification

The reference catalog is a 2026-10-01 snapshot of 56 public hero entries. It is explicitly dated; abilities/season windows can change. Live Custom combat stats, authenticated crosshair edits/votes, LFG posting, Rank Me, custom account leaderboards, OBS/desktop video/hero-swap products and private-data access are not implemented as if they were public statistics endpoints.

53 automated tests pass. Tests use captured public responses and cover mode/schema compatibility, fallbacks, identity-based merging, conflicts, damage/time semantics, pagination/deduplication, filter-bound cursors, all-season isolation, caching, rate limits/privacy and packaged reference data. Live smoke checks confirmed GS-4's three S10 Custom matches, a 12-player match with hero detail, GS-'s enriched hero stats, 24 teammate and 16 opponent encounters, and 77 rank-history matches at test time. Counts can change.

## Automatic best-data selection

The policy does not permanently rank a website above another. It applies these rules:

1. Reject invalid values and incompatible player/match, season, mode, count-basis or unit comparisons.
2. Prefer completed match detail over a summary or known incomplete response.
3. Prefer a newer genuine update time when all comparable competing records have trustworthy update times. Player activity, expiry dates, sentinel dates and unknown ages are not evidence of freshness.
4. Prefer agreement between a strict majority of distinct, comparable providers. Repeated reads from one site do not create additional votes.
5. If no evidence resolves the disagreement, retain the existing value and mark the choice uncertain.

Games, wins and losses move together. When their source changes, win rate is recalculated and old-population averages are recomputed from the selected source's totals. Fields unavailable for that selected population become null rather than carrying an incompatible average. Raw alternatives remain inspectable.

`player.career_summary` holds separately scoped overall competitive career matches. `player.win_rate`, the MCP player tool and the dashboard use this summary when available. Raw `rank_game_season` records stay intact: rank-system battle counts and career counts are different reported measures. Hero participation counts are also separate from overall matches. For the audited GS- example, this permits reporting 44/77 overall career wins/matches while retaining the rank system's 79 battle count and the hero's separate participation count.

Tracker time values are normalized according to `TimeSeconds` or `TimeMilliseconds`; ambiguous formats remain raw. `enrich=False` still keeps the original single-provider behavior.

Source choice is evidence-based and cannot guarantee which provider is factually correct when their reporting or coverage differs. Uncertainty is explicit; no maximum-count or website-popularity shortcut is used.
