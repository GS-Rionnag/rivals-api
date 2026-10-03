# Multi-provider integration

The client now combines RivalsData, RivalsTracker and Tracker.gg public reads. Existing method names, required arguments, typed Mapping responses and primary fields remain supported. No account mutations, refresh queue requests, voting, posting or messaging are performed.

```python
from rivals_api import RivalsClient

with RivalsClient(use_browser_fallback=True) as client:
    player = client.get_player(691218686)
    page = player.matches.fetch(limit=25, mode="custom", season=20, cached=False)
    complete_history = player.matches.fetch(limit="all", mode="custom", season=20)
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
- History's `next_cursor` is opaque and must be reused with the same UID, season, mode, hero, teammate and cached setting. Federation uses all three providers' pagination and deduplicates across pages. Tracker.gg uses the verified name cached by player lookup and its returned `metadata.next` token. Numeric `fetch(limit=...)` stops at the requested merged row count and preserves excess provider rows in its cursor; `limit="all"` traverses the available history. Page boundaries are resumable, but do not guarantee a globally sorted order across provider pages. `player.matches.iter(...)` exhausts all available history. Numeric modes and quickplay/competitive/custom names resolve to IDs 1/2/3. Empty histories are coverage observations, not evidence of no player activity.
- Tracker.gg history rows can lack season IDs, and its season selector can cross seasons. An exact-season query accepts only rows with an explicit season or a season verified by another source for the same match ID. Skipped unverified rows are reported in `provider_metadata.errors`. An unseasoned query can include these rows without inventing a season. Missing verified player names and unsupported teammate filters are also reported explicitly.
- RivalsTracker cannot apply a teammate filter. Such requests retain RD filtering and explicitly report that the alternative provider was skipped. Explicit season/mode/hero filters are checked on all rows, including uncached responses that ignore upstream selectors. Uncached teammate filtering verifies same-team membership from full match detail; this costs additional reads.
- Tracker hero participation counts may be fractional. Raw stat keys/display labels are retained. `totalDamageTaken` is never silently relabeled as the client's `blocked` statistic; RT's opaque `last_kill` is preserved under its source key.
- Provider response caches are independent and close with the client. The calculated-history cache is shared within the Python process (bounded to 16 history sets and 500 match details), so `method="cached"` can reuse a prior full-history query across client instances. A full fetch that had provider errors is still cached, but its result records incomplete coverage; cached calculations make no requests to fill gaps. Browser contexts are reused during a client lifetime and close on exit. Use the synchronous client on the thread that created its browser context.

## Combined match details

Every `Match` returned by `player.matches.fetch(limit=...)` or
`player.matches.iter(...)` carries its originating client. Call
`match.get_details()` inside that client's context to lazily return a **new**
`Match` with typed `MatchTeam`, `MatchPlayer`, and `Character` records. Fetching
history makes no eager detail requests. `client.matches.get(match_id)` and MCP
`get_match(match_id)` use the same combined fetcher. With `enrich=False`, it
requests only RivalsData; the public methods are otherwise identical.

The fetcher validates the returned match ID before accepting each response.
RivalsData and RivalsTracker players merge by numeric game UID. Tracker account
UUIDs remain separate: a cross-provider bridge requires a unique exact player
name and matching team within the same match. Ambiguous identities stay in
`provider_metadata.unmatched_players` and the raw responses; they cannot vote
on another player's stats. Missing roster entries and hero segments are added
when their identities can be resolved. Hero segments match by hero ID within
their verified player. Team and hero row order is never used for identity.

`participant.accuracy_percent` and `hero.accuracy_percent` use percentage units.
Legacy RD `participant.accuracy` remains a percentage, and `hero.accuracy` remains
a ratio. These have provider-specific formulas; unit normalization does not
establish that player and hero accuracy measure the same thing. RT/Tracker
`session_hit_rate` remains a separate ratio and never fills a missing accuracy.
Invalid, non-finite, or out-of-range accuracy values become unavailable. Damage
taken remains separate from damage blocked. Tracker's original stat keys and
display metadata remain under `tracker_stats`.

`provider_metadata` includes:

- `sources`, `evidence`, `selections`, `observations`, and `conflicts` on the
  match and each merged player/hero record. Completed details outrank incomplete
  data; comparable source agreement may resolve a discrepancy. A two-source tie
  remains uncertain and keeps its alternatives. Agreement is not in-game proof.
- `responses`: accepted original payloads keyed by source, without transport
  credentials. Non-finite raw numbers are represented as text for valid JSON.
- `errors`: provider failures and rejected responses for this lookup.
- `completeness`: whether player details exist, which provider records have
  completion evidence, whether all requested reads succeeded, and the number
  of unmatched players. This is not a guarantee of a complete in-game roster.
- `fetched_at`: lookup time, not the provider's data freshness.

Provider failures retain successful details; all providers failing raises a
typed error. Partial results remain in the process-level calculation cache but
are retried on subsequent detail lookups. Completed results are cached by
match ID **and enrichment mode**; cached objects are copied before returning.
Pass `refresh=True` to `match.get_details()`, `client.matches.get(...)`, or MCP
`get_match` to bypass the detail and provider response caches. This performs
read requests, not an upstream refresh-queue mutation. Manually constructed
unbound matches require `client.matches.get(match.match_uid)` instead.

## Existing functions with additions

| Function | Addition |
|---|---|
| `client.get_player(...)` | RT fallback, section visibility and missing profile fields |
| `player.matches.fetch(limit=..., ...)` | Combined history; numeric limits stop after that many merged matches and return a resumable cursor; `limit="all"` traverses all pages. Both deduplicate and report source errors. |
| `client.matches.get(...)` | Per-hero match K/D/A, advanced combat/hero segments and completeness flags |
| `player.stats.win_rate(...)` / `player.matches.fetch_win_rate()` | Intact season career counts selected per mode and checked against combined history; explicit partial fallback |
| `player.stats.hero_win_rates(...)` | Canonical longest-played-hero results with coverage and automatic caching |
| `player.stats.class_win_rates(...)` | Canonical class results from the same match assignments |
| `player.stats.heroes(...)` | Hero list with direct counts and selected-mode nested counts |
| `player.stats.classes(...)` | Class list grouped from one hero assignment per match |
| `player.stats.summary_heroes(...)` / `summary_classes(...)` | Provider participation summaries and available career combat/playtime fields |
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

The read-only tools cover the new functions and the previously Python-only crosshairs, proficiency, punishments, name history, hero leaderboard, public profile and favorites. The match-history tool accepts `cached=False` and mode names. Overall and hero/class tools use automatic calculations without a method argument. All default to Competitive plus Quickplay (`mode="all"`), with single-mode selectors available.

### Canonical season win rate

`player.stats.win_rate(season=None, mode="all")` defaults to the current season
and Competitive plus Quickplay. `mode="competitive"` and `"quickplay"` select
one queue. The same mode options/default apply to hero/class methods and MCP
tools. `"all"` excludes Custom/Arcade; provider `mode=all` overviews and RT
`total_matches` can include other queues and are not used for this calculation.

Records keep games/wins/losses together per source and mode. RT ranked/unranked
career counters and Tracker scoped overview segments are compared after scope,
identity and integer-count validation. RD rank battle counters are retained as
ineligible observations because the count basis is not established as career
matches. Counts below known history totals/wins/losses are rejected. Source
agreement, exact history-count agreement, and credible record update times
when available support selection. Unresolved ties keep an intact deterministic
record with explicit uncertainty/conflicts; rates are never averaged.

The rate is selected wins / games * 100. For `"all"`, selected counts from the
two disjoint modes are summed before division. Missing career records fall back
to deduplicated known history outcomes and are labeled partial. Completed detail
can resolve disputed or missing summary outcomes independently of hero playtime.
Unknown outcomes never become losses in the fallback denominator. Zero games
returns a null percentage. `season="all"` uses tracked-history fallback rather
than mistaking a default-season career record for lifetime counts.

Metadata carries selected sources, scoped per-mode records, rejected/alternate
observations, disagreements, history counts, unknown outcomes, and errors.
History agreement supports the record without claiming complete game coverage.
Caching is automatic and scoped by player, season, mode and enrichment setting.
Unresolved disagreements, unknown outcomes and request failures are retried.

### Canonical hero/class win rates

`player.stats.heroes()` and `player.heroes.fetch()` list match-attributed heroes.
`player.stats.classes()` groups those same assignments by class.
`hero_win_rates()` / `class_win_rates()` return `data` plus `metadata`, retaining
coverage even when no rows can be attributed. Mode defaults to Competitive plus Quickplay (`"all"`);
season defaults to Tracker profile `currentSeason`. An unavailable default
season requires an explicit numeric ID or `"all"`. All-seasons history sends
no season selector, rather than the provider-summary `-1` selector.

Each deduplicated match is assigned once to the unique hero with the most
per-match playtime. The result goes to that hero and its class. Complete source
records are evaluated independently; their durations are never blended.
Equal maximum times, invalid/missing durations, duplicate heroes, uncertain
player identity, conflicting longest heroes, and unknown/conflicting outcomes
remain unresolved. Completed player outcomes take precedence over summaries;
a known summary outcome is used only when completed details have none.
There is no summary-hero attribution fallback. Win rates are computed from
assigned wins/losses, with integer `win_rate` and two-decimal `win_rate_pct`.

Metadata contains resolved scope, sources, provider errors, per-match assignments,
unresolved reasons, and counts of found/attributed/unresolved matches. Unknown
class mappings can reduce class attribution relative to hero attribution.
Complete game-history coverage is never claimed. Assigned `play_time` covers
the chosen hero only in the matches attributed to it, not all hero participation.
Exact-season queries retain the history fetcher's explicit season limitations.

Detail caches are reused automatically. Hero and class calculations share a
bounded per-client cache using `provider_cache_ttl`; errors/unresolved matches
prevent caching a final calculation so another request can retry them.
First calls can require one combined detail lookup per match.

### Migration and provider summaries

Former provider hero/class definitions remain under `summary_heroes(mode=...)`,
`summary_classes()`, and `player.heroes.summary()`. Canonical hero rows preserve
selected-mode nested stats plus direct counts, but cannot supply career combat
totals or leaderboard ranks (`rank=None`). Class responses retain `.classes`.
MCP hero-list/stat tools now return a `data`/`metadata` envelope and default to
Competitive plus Quickplay. Overall and hero/class MCP tools no longer expose `method`.

Python `matches.fetch_hero_win_rates()` / `fetch_class_win_rates()` default to
canonical attribution; explicit `exact` is an alias. Explicit legacy `estimate` with a single mode
keeps provider summary estimates, while `cached` uses existing history/details
without requests and reports unresolved attribution. Overall `matches.fetch_win_rate()` aliases `stats.win_rate()`. Explicit legacy
Python method overrides remain available for specialized history calculations.
The profile `player.win_rate` convenience remains a competitive profile snapshot,
not the new verified season request.

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
