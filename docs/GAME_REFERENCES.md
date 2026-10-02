# Readable game references

`Match` exposes `map: Map`, `game_mode: GameMode`,
`gameplay_mode: GameplayMode` (`game_play_mode` is an alias),
`platform: Platform`, `rank: Rank`, `season_info: Season`, and `hero: Character`.
Unavailable references are `None`. Printing or formatting a reference uses its
name; `.name` returns a string, `.id` retains its upstream identifier.
`Map.location` gives the broader location. `match.winner` references the winning
`MatchTeam` when known; `match.result` gives Victory, Defeat, or Draw when the
response establishes it. Team names are neutral Team 1/Team 2 labels; they do
not claim which side attacked or defended. Match and participant `.id` aliases
their respective match/game-player identifiers.

`MatchPlayer.hero` uses an explicitly reported hero or top hero, retaining the
corresponding Character's segment statistics when available. `top_hero`,
`rank_info`, and `platform_info` resolve their corresponding fields. Draft
entries have typed `hero` and `team` references. Stats records with `rank_level`,
`season`, `os`, or `login_os` expose `rank_info`, `season_info`, or
`platform_info`; player profiles also expose `platform_info`. Numeric fields
remain available. Account IDs, replay identifiers, party IDs, cosmetic IDs and
other opaque identifiers are preserved as reported: no established name
catalog was found for them, and party identifiers are not treated as match
team camps.

## Serialization and compatibility

References are mapping-compatible models. `match["map"].name` and
`match.map.name` are equivalent. `to_dict()` recursively serializes references
into ordinary JSON objects with `id`, `name`, `is_known`, `source`, and any
type-specific fields. It retains legacy `map_id`, `game_mode_id`,
`game_play_mode_id`, `season`, `hero_id`, and `rank_level` fields.

`match.platform` now holds a `Platform`; use `.platform_id` or `.platform.id`
for the original scalar. Serialized matches include both `platform_id` and the
structured `platform`. `.raw` remains the original input, including numeric
platform values on responses fetched from providers. Models round-trip through
`Match(match.to_dict())` without losing labels or nested Character types.

Unknown codes retain their IDs, display `Unknown map`, `Unknown platform`,
etc., and report `is_known=False`. No label is inferred by truncating a number,
guessing a future season, or treating every console as PlayStation. Known
provider labels can resolve a new map even before the packaged catalog changes.
Names are resolved locally; constructing history references makes no detail or
metadata requests. `get_details()` also fills missing map/queue/platform/season
context from the same history match, recording those fields and their sources
under `provider_metadata.history_context`. Detail values take precedence.

## Catalog evidence (checked 2026-10-02)

The packaged `src/rivals_api/game_catalog.json` contains 118 map variants and
20 verified season identifiers. It prefers the specific map names from
[RivalsData's current public match catalog](https://rivalsdata.com/assets/matches-BtVAubcc.js)
and fills additional variants and location labels from
[RivalsTracker's public map catalog](https://rivalstracker.com/_nuxt/CUE0zxkU.js).
For example, `1288` is **Hell's Heaven**, location **Hydra Charteris Base**,
objective **Domination**; `1245` is **Spider-Islands**, objective **Convoy**.
Provider-supplied `map_name` / `map_mode_name` values take precedence when usable.
The catalogs contain provider-maintained labels; resolving a label is not a
claim that every provider label has been independently verified in-game.

Queue codes `1/2/3/4` mean Quick Match / Competitive / Custom / Arcade. Code 5
is Tutorial in RivalsTracker; 7 is Practice vs AI; 9/10 are Tournament. Sources
disagree about code 6: RivalsData labels it **Duel**, RivalsTracker **Practice**.
The model follows the selected field's provider when available, exposes both
under `.alternatives`, and reports an unknown name if its source is unestablished.
See the [RivalsData catalog](https://rivalsdata.com/assets/matches-BtVAubcc.js)
and [RivalsTracker match UI](https://rivalstracker.com/_nuxt/DDKdWPNg.js).

The raw `game_play_mode_id` has no verified universal objective-name mapping.
The same code `200` can be returned for different map objectives. Accordingly,
`GameplayMode.name` comes from the match's `map_mode_name` or its map variant's
catalog entry. Its `.id` retains the raw gameplay code and `.map_id` records the
context. Without a known map/objective it stays unknown. It must not be used as
a global `200 = Convoy` lookup.

Platform codes **1 = PC, 2 = PlayStation, 4 = Xbox** are established by both
[RivalsData's leaderboard platform options](https://rivalsdata.com/assets/index-B7e1fRs3.js)
and [RivalsTracker's leaderboard](https://rivalstracker.com/_nuxt/C7pX95rV.js).
Code 3 is unestablished, so it remains unknown. Platform strings such as `pc`,
`psn`, and `xbl` retain their original string ID while resolving their name.
Rank levels and divisions follow the
[provider rank catalog](https://rivalsdata.com/assets/ranks-D6blxaOO.js), with
RivalsTracker's observed levels 23–25 labeled One Above All. These are rank
levels, not hero-stat tier filter IDs, which use a different numbering scheme.
Season labels follow that same RivalsData catalog and the recorded Tracker
profile season metadata: internal ID 20 is Season 10, 19 is Season 9.5, and
1 is Season 0. No future season label is extrapolated.

Catalog updates should verify the current public assets and retain map variant
keys; several RivalsTracker entries have an inner `ModeID` that differs from
their dictionary key. The variant dictionary key is the lookup identifier.
