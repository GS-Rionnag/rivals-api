# GS-4: RivalsData versus RivalsTracker

## Correction: competitive history coverage (2026-10-03)

The earlier two-provider snapshot below does not establish that GS-4 has no
recent competitive matches. Tracker.gg's public GS-4 history returned 25 rows
on its first page, including 15 competitive matches. The newest competitive
match was `5521403_1790383734_1231008_11001_11`, timestamp
`2026-09-26T01:01:44+00:00`. RivalsData's cached competitive request returned
an empty list, while RivalsTracker's competitive API request now returned 20
rows, including that same match. These are first-page observations, not total
match counts or proof of complete coverage. The user's observation that the
RivalsTracker site showed no recent competitive matches remains distinct from
the API response obtained in this check.

The client previously federated only RivalsData and RivalsTracker histories,
despite using Tracker.gg for other sections. Combined history now also queries
Tracker.gg by the verified in-game name, follows its returned pagination token,
and retains source errors and disagreements. An empty provider history describes
that response's coverage; it does not demonstrate that the player did not play.
Tracker rows without verified seasons are excluded from exact-season queries
with an explicit coverage error, since its season selector can cross seasons.

Public source: [GS-4 on Tracker.gg](https://tracker.gg/marvel-rivals/profile/ign/GS-4/).
Local read-only captures: `dist/gs4-history-current.json` and
`dist/gs4-profile-current.json`. Regression data is packaged in
`tests/fixtures/gs4_tracker_history.json`.

## Earlier two-provider snapshot

Checked 2026-10-01, UID 691218686, season 20. This is a single-profile
comparison of API responses, not a site-wide accuracy benchmark. Raw responses
are saved in `dist/site-comparison/responses.json`.

| Category | RivalsData | RivalsTracker |
| --- | --- | --- |
| Accessible history | 12 cached matches, all Quickplay; direct history returns private | 16 matches: 13 Quickplay and 3 Custom |
| Latest retrieved match | September 21, 2026, 12:49 PM Eastern | September 28, 2026, 1:16 AM Eastern |
| Earliest retrieved match | September 12, 2026, 10:32 PM Eastern | September 12, 2026, 10:55 PM Eastern |
| Quickplay win rate from retrieved history | 6/12 = 50% | 4/13 = 30.8% |
| Custom history | No cached entries | 0 wins out of 3 |
| Competitive profile record | 11/26 = 42.3%, score 3493.268735726848 | Same record in profile info; separate stats report 0 tracked competitive matches |
| Hero aggregate rows | 4 Quickplay heroes; no competitive hero data | 7 unranked hero entries, including 2 with zero counted matches but positive playtime; ranked empty |
| Hero playtime | No cumulative playtime in hero aggregate endpoint; present in match details | Present in hero aggregates and per-hero match details |
| Map aggregate entries | 9 | 11 |

History pagination was exhausted for both sources in season 20. Their match
sets share only four IDs, with 8 RivalsData-only and 12 RivalsTracker-only IDs
(24 unique matches combined). All four shared match summaries agree on K/D/A
and win/loss. The different match populations prevent using the differing
Quickplay rates to declare one source numerically wrong or GS-4's performance
better/worse.

Hero examples: RivalsData reports Daredevil 3 wins/7 games (42.9%), while
RivalsTracker reports 0/6 (0%). RivalsData reports Blade 2/2 (100%), while
RivalsTracker's Blade entry has zero counted games and 114.655988 seconds
playtime. These are different aggregations and populations, not equivalent
samples. RivalsTracker's seven entries are not seven heroes with counted games.

Both sites return 12 player rows for shared match
`5513982_1789267345_1411259_11001_12`. GS-4's K/D/A is 34/5/2 on both.
Damage and healing match after rounding: 18148 and 1757. RivalsData includes
per-player totals and per-hero playtime/accuracy; RivalsTracker also includes
per-hero K/D/A. RivalsData identifies the most-used hero as Gorr, whereas
RivalsTracker's `cur_hero_id` is Blade; these fields should not be treated as
having the same meaning. RivalsData labels a field `blocked`, while
RivalsTracker labels its corresponding numeric value `total_damage_taken`;
the semantic difference requires verification before combining those fields.

RivalsData also returns full details for GS-4's Custom match
`5517895_1790571442_1267080_11001_11` when supplied its ID directly, despite
not listing the match in cached history. This is a discovery/visibility gap,
not proof RivalsData cannot serve Custom match details.

For GS-4, RivalsTracker is the better source for discovering recent and Custom
matches and obtaining aggregate hero playtime. RivalsData offers richer
normalized hero averages (per game/per 10, team-up records) and contributes
matches absent from RivalsTracker. Neither retrieved history is established as
complete; both retrieved histories in that snapshot showed no competitive matches despite their profile info
recording 26 competitive games. A combined client should preserve source,
season, mode, and metric definitions and deduplicate by match ID.

Sources: https://rivalsdata.com/player/691218686 and
https://rivalstracker.com/profile/691218686. Endpoint details for RivalsTracker
are documented in `RIVALSTRACKER_API.md`; RivalsData endpoints in `API.md`.
