# RivalsTracker API observations

Verified on 2026-10-01 from the public GS-4 profile and its frontend assets.
These are undocumented website endpoints, not a guaranteed supported API.
Base URL: `https://api.rivalstracker.com/api`.

## Verified read endpoints

All three endpoints returned HTTP 200 JSON without a login, cookie, or API key
in the tested requests.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/player/691218686` | Profile, visibility, stats, and initial match history. Frontend also supplies `season=20`. |
| GET | `/player-match-history/691218686?skip=0&game_mode_id=3&hero_id=0&season=20` | Three Custom matches for GS-4 in season 20. |
| GET | `/matches/5517895_1790571442_1267080_11001_11` | Completed Custom match details, including 12 player rows. |

The frontend advances `skip` by 20 for pagination. `game_mode_id=0` and
`hero_id=0` are its initial unfiltered selectors; Custom uses `game_mode_id=3`.
For this profile, `skip=20` with the Custom filter returned an empty array.
Omitting `season` from the filtered history request also returned three matches;
the default season semantics were not established.

History is a JSON array. Each row includes `match_uid`, `game_mode_id`,
`match_map_id`, `match_play_duration`, `match_time_stamp`, `match_season`,
`match_winner_side`, score information in `dynamic_fields.score_info`, and
`match_player` containing `k`, `d`, `a`, `is_win`, `camp`, and a hero ID.

Match details include a `match_players` array. Rows contain `player_uid`,
`nick_name`, `camp`, `is_win`, `k`, `d`, `a`, `total_hero_damage`,
`total_hero_heal`, `total_damage_taken`, `last_kill`, `session_hit_rate`,
`solo_kill`, and `player_heroes`. Each hero segment supplies hero ID,
kills/deaths/assists, and play time in seconds. `total_damage_taken` should not
be interpreted as damage blocked. The meaning of `last_kill` was not verified;
the raw field name is preserved here.

## Confirmed GS-4 example

Match ID: `5517895_1790571442_1267080_11001_11`.
Custom (`game_mode_id=3`), Hall of Djalia (`match_map_id=1267`), duration
889.816895 seconds. GS-4 lost 2–3 and recorded 28 kills, 5 deaths, 7 assists,
16871.345252 damage, 0 healing, 32646.957813 damage taken, and 3 solo kills.
Hero segments were Venom (1035): 5/5/2 over 370.944804 seconds, and
Hulk (1011): 23/0/5 over 518.823055 seconds.
Replay ID: `107145115403`.

Raw responses captured for inspection are in `dist/rivalstracker-research/`.
No RivalsTracker integration was added to the package. Refresh actions,
rate limits, complete historical coverage, other platforms, and long-term
availability remain unverified.

## Expanded audit

See [expanded API contracts](RIVALSTRACKER_API_AUDIT.md), [Tracker.gg API](TRACKER_NETWORK_API.md) and [complete feature gaps](PROVIDER_FEATURE_GAPS.md) for the broader 2026-10-01 research.
