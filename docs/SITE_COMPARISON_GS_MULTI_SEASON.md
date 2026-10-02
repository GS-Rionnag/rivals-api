# GS- across three sites and seasons

Observed 2026-10-01. GS- UID: 1970288503. Sources:
[RivalsData](https://rivalsdata.com/player/1970288503),
[RivalsTracker](https://rivalstracker.com/profile/1970288503), and
[Tracker Network](https://tracker.gg/marvel-rivals/profile/ign/GS-/).
Tracker Network was accessed with this project's installed Camoufox. Direct
API requests were challenged; ordinary in-browser requests succeeded.

Season labels were verified against tracker.gg profile metadata:
18 = S9, 19 = S9.5, 20 = S10. Raw responses, browser capture, and example
match details are saved in `dist/gs-season-comparison/`.

## Competitive records

This table uses RivalsData's season rank/profile record, RivalsTracker's
tracked competitive totals, and tracker.gg's Competitive overview segment.
It intentionally does not substitute summed hero records for player records.

| Season | RivalsData profile wins/games | RivalsTracker wins/games | tracker.gg wins/games |
| --- | --- | --- | --- |
| S9 | 29/61 = 47.5% | 29/61 = 47.5% | 29/61 = 47.5% |
| S9.5 | 20/38 = 52.6% | 20/38 = 52.6% | 20/38 = 52.6% |
| S10 | 44/79 = 55.7% | 44/77 = 57.1% | 44/77 = 57.1% |

GS-'s season competitive win rate improved across these periods. The current
season denominators differ, so the exact improvement depends on source scope.
RivalsData's cached S10 history itself contains 77 competitive matches, 44
wins, 31 losses, and 2 draws. Its hero stats count 75 Loki games, 44 wins and
31 losses. This demonstrates why profile, history, and hero denominators
cannot be interchanged. The reason for the profile's extra two games was not
established.

## History coverage

RivalsData cached and RivalsTracker histories were paginated to exhaustion
with the season selector. tracker.gg history pagination was sampled through
15 pages per season (375 distinct IDs per traversal), sufficient to find all
IDs retrieved from the other sources. Those tracker.gg traversals continue
into earlier seasons; 375 is not a season match count. Exhaustive tracker.gg
lifetime history was not requested or established.

| Season | RivalsData cached matches | RivalsTracker matches | RivalsTracker Custom matches | tracker.gg coverage of those IDs |
| --- | --- | --- | --- | --- |
| S9 | 95 | 127 | 16 | All 127 RivalsTracker IDs and all 95 RivalsData IDs found |
| S9.5 | 92 | 95 | 3 | All 95 RivalsTracker IDs and all 92 RivalsData IDs found |
| S10 | 93 | 92 | 0 | All 93 RivalsData IDs and all 92 RivalsTracker IDs found |

All RivalsData S9 and S9.5 cached IDs are subsets of RivalsTracker's IDs. The
S9 deficit is 6 Competitive, 8 Quickplay, 2 Arcade, and 16 Custom matches.
The S9.5 deficit is 3 Custom matches. In S10, RivalsData contributes one
Quickplay match absent from RivalsTracker:
`5517599_1790816376_1420352_11001_11`. tracker.gg contains it.
tracker.gg exposes `custom-game` in history responses even though its profile
mode menu did not offer a Custom filter during inspection.

## Shared-match consistency

Comparing RivalsData summaries against tracker.gg summaries by exact match ID:

| Season | Shared matches checked | Kills differ | Deaths differ | Assists differ |
| --- | --- | --- | --- | --- |
| S9 | 95 | 0 | 0 | 0 |
| S9.5 | 92 | 14 | 3 | 29 |
| S10 | 93 | 1 | 1 | 17 |

These are field mismatch counts; a match can differ in more than one field.
Win/loss agrees in comparisons where tracker.gg explicitly labels win/loss;
draw labeling was not treated as a loss comparison.

One internally verified tracker.gg inconsistency:
match `5513426_1788985360_1245106_11001_12` has summary K/D/A 8/12/12.
tracker.gg full details give 8/12/1, as do RivalsData's summary and full details
and RivalsTracker's summary and full details. This establishes a summary versus
detail inconsistency, not that every tracker.gg mismatch has the same cause.
It also means agreement between sites alone should not be treated as proof of
ground truth.

## Hero metrics

| Competitive example | RivalsData | RivalsTracker | tracker.gg |
| --- | --- | --- | --- |
| S9 Black Panther | 5/10, 50% | 5/12, 41.7% | 5/12.2, 41.0% |
| S9.5 Hulk | 7/9, 77.8% | 7/9, 77.8% | 5.8/7.6, 76.3% |
| S10 Loki | 44/75, 58.7% | 44/77, 57.1% | 44/75, 58.7% |

tracker.gg's fractional matches and wins are literal API values. The hero
attribution formula was not established, so those counts should not be called
whole matches or compared directly with integer hero attribution.

RivalsTracker reports S10 Competitive Loki playtime of 55829.988864 seconds
(15.51 hours), while tracker.gg reports 4648.776 seconds (1.29 hours).
RivalsData does not expose cumulative hero playtime in its hero aggregate
response. It does expose playtime per hero in match details. The tracker.gg
total appears substantially incomplete or scoped differently; its exact cause
was not established. In S9 Competitive, the sites' Black Panther playtime totals
are much closer: RivalsTracker 7987.356448 seconds versus tracker.gg 7987.346
seconds. Playtime disagreement is therefore not a universal unit conversion.

Combat hero totals also differ. S10 Competitive Loki assists: RivalsData
approximately 2017 when multiplying its rounded per-game average by 75 games;
RivalsTracker's raw total 2073; tracker.gg raw total 1771. Multiplying a rounded
average is an approximation, not an exact aggregate. Population, draw handling,
hero attribution, and observed tracker.gg summary inconsistencies all warrant
keeping these datasets separate.

## Assessment

For this account and these seasons, tracker.gg is strongest in verified match
ID coverage and offers a useful season overview, rankings, roles, and hero
playtime interface. Its internal summary/detail inconsistency and incomplete
or differently scoped playtime prevent treating it as an unquestioned reference.

RivalsTracker offers stronger historical coverage than RivalsData in S9/S9.5,
Custom-match discovery, per-hero combat segments, and useful playtime totals.
It misses one S10 Quickplay match present on both other sources.

RivalsData offers convenient normalized hero averages, per-10 metrics,
accuracy, and team-up breakdowns, but its cached history and older hero
aggregates have material coverage gaps. Its profile record can be fresher or
broader than its detailed history.

No site wins every category. For the package, prefer RivalsTracker plus
RivalsData as complementary sources; use tracker.gg for cross-checking match
coverage and competitive season records, and inspect full details when its
summaries disagree. This is a three-season, one-account observation, not a
site-wide benchmark or proof of in-game accuracy.
