# Complete observed provider feature gaps

Audit date: 2026-10-01. Compared public RivalsTracker and Tracker.gg surfaces/API responses against this repository’s current Python client, models, resources and MCP/dashboard. Scope is all gaps identified from the observed surfaces, not a claim to enumerate either provider’s private backend. This inventory describes the pre-integration audit. The subsequent implementation is documented in [provider integration](PROVIDER_INTEGRATION.md).

RT = RivalsTracker; TRN = Tracker.gg; RD = existing RivalsData source. Missing means absent from the supported current surface; Partial means an existing feature needs richer data/scope. UI/account/advertised features are not proven anonymous API endpoints. Unknown fields are preserved by current Mapping models, so a missing typed field alone is not counted as missing data.

References: [RT API](RIVALSTRACKER_API_AUDIT.md), [TRN API](TRACKER_NETWORK_API.md), [season comparison](SITE_COMPARISON_GS_MULTI_SEASON.md).

## Provider access and coverage

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G001 | RivalsTracker provider integration | RT | Missing | Numeric UID profile/search/history/full-match access. |
| G002 | Tracker.gg provider integration | TRN | Missing | IGN profile/career/history/full-match access through browser-compatible transport. |
| G003 | Provider fallback for missing/private/cached histories | Both | Missing | GS-4 has Custom matches on RT while RD cached history did not. Custom history itself already exists in RD. |
| G004 | Multi-provider match merge and deduplication | Both | Missing | Use stable match IDs; preserve source and completeness rather than adding provider counts. |
| G005 | Source/season/mode/coverage discrepancy reporting | Both | Missing | Expose differing wins/matches/playtime and summary/detail disagreements. |
| G006 | Permission and freshness diagnostics | Both | Partial | RT visibility by section; TRN private flags/expiry; current 403 handling can confuse private history with Cloudflare. |
| G007 | Multi-result player search | RT | Partial | RT find-player returns candidates; current resolver selects a matching single result. |
| G008 | Provider season catalog and display names | TRN | Partial | Current integer season selectors exist; TRN supplies named full/half seasons and current/default IDs. |
| G009 | Provider mode catalog and additional career modes | TRN | Partial | Current hero/class career tools cover competitive/quickplay; TRN advertises all/arcade/18v18/tournament/event, availability per player varies. |

## Player progression and history

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G010 | Rank rating timeline | Both | Missing | Timestamped rank/rating history. |
| G011 | Match-linked before/after rank score | RT | Partial | Existing match score change exists; RT adds timeline before/after scores and levels. |
| G012 | Promotion/demotion events and counts | RT | Missing | Explicit transitions and season summary. |
| G013 | Season progression summary | RT | Missing | Starting/current/peak score, net score and largest gain/loss together. |
| G014 | Named season peaks and lifetime best presentation | TRN | Partial | Existing player raw seasonal ranks exist; named peaks/all-time best and display assets need normalization. |
| G015 | Expanded name history | RT | Partial | Existing names/first_seen; adds last detected, match counts, current flag. |
| G016 | Name-change event trail | RT | Missing | Previous name, detected time and source match. |
| G017 | Historical punishment records | RT | Partial | Current player punishments covers login/rank/chat state; RT adds dated historical array with reason/type/duration/expiry. |

## Player cosmetics

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G018 | Per-player skin usage catalog | RT | Missing | Observed hero/skin combinations; not ownership. |
| G019 | Skin performance stats | RT | Missing | Matches, wins/losses, win rate and playtime per used skin. |
| G020 | Skin first/last use and season history | RT | Missing | Usage timestamps and seasons. |
| G021 | Cosmetic coverage summary | RT | Missing | Analyzed matches, unique skins, covered heroes and total skin playtime. |

## Combat and career detail

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G022 | Cumulative hero playtime and winning playtime | Both | Partial | Match playtime exists; no equivalent hero career playtime aggregate API in current build. |
| G023 | Rich role combat totals and rates | TRN | Partial | Existing classes derive games/wins/losses/MVP/SVP; add K/D/A, playtime, damage/healing/damage-taken and per-minute values. |
| G024 | Per-hero K/D/A within a match | Both | Partial | Current overall player K/D/A and hero usage exist; RT/TRN offer hero-specific K/D/A. |
| G025 | Per-hero match damage/healing/damage-taken breakdown | TRN | Partial | Existing overall player totals; TRN hero segments add the breakdown. |
| G026 | Head-kill totals | TRN | Missing | Match and career headKills. |
| G027 | Kill-streak and survival-streak stats | TRN | Missing | maxSurvivalKills/maxContinueKills and hero survival/continue fields. |
| G028 | Triple/quad/penta/hexa kill counters | TRN | Missing | continueKills3/4/5/6; source terminology preserved. |
| G029 | Attack and hit counters | TRN | Missing | mainAttacks/mainAttackHits; existing accuracy alone is not these counters. |
| G030 | Shield/summoner/chaos hit breakdowns | TRN | Missing | Separate hit target/source counters; meanings require care. |
| G031 | Detailed hit-rate numerators/denominators | TRN | Partial | Existing accuracy; adds use, hero/ally/enemy/shield/summoner/chaos hit counts for feature slots 1/2. |
| G032 | Critical hit-rate numerators/denominators | TRN | Partial | Existing critical accuracy; adds crit-hit/hit counts for feature slots 1/2. |
| G033 | Hero-specific performance fields | TRN | Missing | featureNormalData1..4, featureSpecialData1Total/Value; typed meanings require hero definitions. |
| G034 | Stat population percentiles | TRN | Missing | Profile stat percentile metadata, e.g. KDA/win%/kills. |
| G035 | Normalized stat display metadata | TRN | Missing | Display names/types/categories/units and raw/display value preservation. |
| G036 | Explicit match completeness flags | TRN | Missing | fullMatchAvailable/fullMatchFetched; current match resource lacks this provider flag contract. |

## Encounters and matchup analytics

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G037 | Player results against enemy heroes | RT | Missing | Per-player matchup matches/wins by enemy hero. |
| G038 | Opponent encounter history | TRN | Missing | Played Against list, frequency and last encounter. |
| G039 | Teammate last-encounter timestamp | TRN | Partial | Current teammate stats exist; add recency. |
| G040 | Encounter rows enriched with other player season stats | TRN | Partial | Rank, season win%, KD and matches alongside encounter stats. |
| G041 | Encounter scope and timezone metadata | TRN | Missing | Season/mode selectors and offset; frontend 75-day default warning. |

## Global meta

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G042 | Global hero matchup matrix | RT | Missing | Hero-versus-enemy-hero matches/wins; not causal proof. |
| G043 | Matchup baseline/delta presentation | RT | Missing | Frontend comparison to hero baseline from matrix; preserve aggregate scope. |
| G044 | Team role-composition meta | RT | Missing | Composition matches/wins by rank, e.g. two of each role. |
| G045 | Rank distribution counts/percentages | RT | Missing | Tracked-player population by rank; derived percentage/mean/median. |
| G046 | Season selectors on global hero meta | RT | Partial | Existing tier list/global detail lacks matching historical season selector. |
| G047 | Explicit mirror-match frequency | RT | Partial | Non-mirror win rate already exists; mirror_matches count is extra. |
| G048 | Ban denominator and slot metadata | RT | Partial | Existing ban rates/player bans; RT adds ban_matches and ban_slots_per_match. |
| G049 | Global hero-by-map performance aggregates | RT | Partial | Existing per-player map stats; RT global heroes/stats supplies each hero’s matches/wins by map. |
| G050 | Combat-stat history for global heroes | RT | Partial | Existing meta trends win/pick/ban; add daily KDA, kills/deaths/assists and damage/healing/damage-taken rates. |
| G051 | Global skin popularity | RT | Missing | Per-skin match counts and per-hero share. |
| G052 | Additional hero-leaderboard metrics | RT | Partial | Hero leaderboard already exists; add cumulative playtime/combat metrics when absent. |

## Hero and game reference data

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G053 | Hero descriptions and identity metadata | Both | Partial | Existing ID/name/role resolver; add biography/real/internal name and hero metadata. |
| G054 | Hero difficulty, attack method and form attributes | RT | Missing | Difficulty/gender/type/usability/new flags plus per-form movement/health/shield/armor. |
| G055 | Active ability/passive encyclopedia | RT | Missing | Names/descriptions/icons/key bindings and ultimate/passive flags. |
| G056 | Team-up descriptions and availability windows | RT | Partial | Existing team-up stats; add anchors/text/icons and active/start/end seasons. |
| G057 | Skin name/quality/image catalog | RT | Missing | Static frontend metadata, distinct from usage stats. |
| G058 | Map/mode/rank display assets | TRN | Partial | Existing IDs/basic fields; consistent names/images/rank colors/short names need catalog normalization. |

## Community crosshairs

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G059 | Public crosshair gallery and discovery | TRN | Partial | Existing player crosshair retrieval; add community listing, pagination/sort/search/pro filters. |
| G060 | Crosshair author/vote/date metadata | TRN | Missing | Score, author/account/pro fields, timestamps and user vote. |
| G061 | Crosshair visual preview and builder | TRN | UI only | Frontend code parser/editor and copy/export flow. |
| G062 | Crosshair create/edit/delete and voting | TRN | Account required; untested writes | Bearer-authenticated client routes discovered; no account mutations performed. |

## Community and app products

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G063 | Looking-for-group listings and filters | TRN | Missing | Public API verified; role/rank/platform/region/language/mic/playlist/timezone and expiry. |
| G064 | Looking-for-group posting/account contact flow | TRN | UI/account; writes untested | Add Me and social/contact metadata shown; no post/contact performed. |
| G065 | Custom group leaderboards | TRN | UI/config verified | Compare selected players; backend creation/schema not established. |
| G066 | Rank Me guessing game and polls | TRN | Account/UI verified | Play, manage/share poll and leaderboard; anonymous page requires login. |
| G067 | Profile claiming and customization | TRN | UI/config verified | Claiming instructions and premium custom avatar/banner/frame fields; no claiming performed. |
| G068 | Desktop live scouting overlay | TRN | Advertised desktop feature | Existing client live roster exists; downloadable in-game overlay is additional. |
| G069 | Hero-swap notifications | TRN | Advertised desktop feature | Requires desktop app; no corresponding public REST alert stream confirmed. |
| G070 | Automatic video highlights | TRN | Advertised desktop feature | Desktop recording/clipping product, not a confirmed stats API. |
| G071 | OBS stream overlays | TRN | Navigation verified | Linked Tracker product; Marvel Rivals widget schema/availability not tested. |
| G072 | Mobile profile tracking app | TRN | Config/product link verified | iOS/Android links; no app API reverse engineering. |
| G073 | Premium presentation and account benefits | TRN | UI verified | Ad-free UI, customization/account features; broader paid entitlements untested. |

## Existing Python capabilities missing from MCP

| ID | Feature | Source | Current gap / evidence status | Detail |
|---|---|---|---|---|
| G074 | Player crosshairs MCP tool | RD | MCP only | Already player.crosshairs.fetch(). |
| G075 | Player proficiency MCP tool | RD | MCP only | Already player.proficiency.fetch(). |
| G076 | Player punishments MCP tool | RD | MCP only | Already player.punishments.fetch(). |
| G077 | Player name history MCP tool | RD | MCP only | Already player.name_history.fetch(). |
| G078 | Hero leaderboard MCP tool | RD | MCP only | Already client.heroes.leaderboard(). |
| G079 | Public profile metadata MCP tool | RD | MCP only | Already client.profiles.get(). |
| G080 | Favorites retrieval MCP tool | RD | MCP only | Already client.favorites.fetch(); no implication that favorites CRUD exists. |
| G081 | Uncached match-history MCP option | RD | MCP only | Python matches.fetch(cached=False) exists; essential when cached history omits Custom matches. |

## Already present: do not count as new

Player lookup/UID resolution; competitive/quickplay hero stats and all-season selection; basic role totals; per-player maps and bans; teammates and their win/loss records; Custom match filtering at Python level; completed full-match rosters/team scores/replay/draft; overall K/D/A, damage/healing/blocked, MVP/SVP, accuracy and hero usage/playtime; live-game roster/rank/top heroes; global tier lists, hero detail, win/pick/ban trends, hero leaderboard and team-ups; punishment/XP/top-500/communication-ban/leaver insights; faction data; basic recent-match dashboard/form. These are existing features, although some have source/scope/MCP gaps above.

## Unverified: not included as confirmed missing features

- Live custom-game combat stats: no successful active payload or public endpoint established.
- Heatmaps, sessions, calendar, best-match tables: generic code/nullable fields are insufficient; no populated Marvel Rivals response established in this audit.
- Working Tracker ranked leaderboard selectors: observed request returned 400.
- Player owned-skin inventory, undocumented private/authenticated endpoints, exact request limits and complete Rank Me/LFG write contracts: not established.
- Enemy party-group analytics: parties field exists, but no populated/usable party aggregate was established; match party IDs already exist in current data.

## Priority for this project

First: provider adapters plus provenance/coverage and uncached MCP history. Then: rank timelines, per-hero match combat stats, enemy encounters, skin usage, hero matchups, team-composition/rank-distribution meta. Expose existing Python capabilities through MCP independently. Community/desktop products are separate product work and do not follow automatically from adding stats endpoints.

## Validation and evidence

81 individually listed gaps/enhancements/product capabilities, including 8 existing-Python/MCP-only entries. This count is an inventory count, not 81 new anonymous endpoints. Captures contain full raw field inventories in the companion API docs. Sources were inspected with local Camoufox and public read requests; account actions/refresh mutations were not executed.

Local audit evidence: `dist/provider-api-audit/`; earlier Custom examples: `dist/rivalstracker-research/`; season comparisons: `dist/gs-season-comparison/`. Baseline inspected: `src/rivals_api/client.py`, `resources.py`, `models.py`, hero IDs, MCP tools and dashboard code. Research files are preserved locally; the docs and JSON inventory are durable review artifacts.

Public sources: [RT GS-](https://rivalstracker.com/profile/1970288503), [RT heroes](https://rivalstracker.com/heroes), [RT compositions](https://rivalstracker.com/team-comps), [RT ranks](https://rivalstracker.com/ranks), [RT skins](https://rivalstracker.com/skins), [TRN GS-](https://tracker.gg/marvel-rivals/profile/ign/GS-/), [TRN encounters](https://tracker.gg/marvel-rivals/profile/ign/GS-/encounters?season=20), [TRN crosshairs](https://tracker.gg/marvel-rivals/crosshairs), [TRN LFG](https://tracker.gg/marvel-rivals/lfg), [TRN Rank Me](https://tracker.gg/marvel-rivals/rank-me/play), [TRN desktop app](https://tracker.gg/marvel-rivals/app).
