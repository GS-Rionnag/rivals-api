# RivalsTracker expanded API audit

Verified 2026-10-01. Base: `https://api.rivalstracker.com/api`. These are observed website endpoints, not a supported public developer contract. See [earlier custom-match examples](RIVALSTRACKER_API.md) and [complete gap inventory](PROVIDER_FEATURE_GAPS.md).

## Successfully tested routes

| Method | Exact tested path | HTTP | Response |
|---|---|---|---|
| GET | `/player/1970288503?season=20` | 200 | matchups, teammates, stats, player, career_settings, visibility, match_history, heroes_ranked, heroes_unranked, maps |
| GET | `/player/1970288503/rank-history?season=20` | 200 | player, season, summary, matches, transitions |
| GET | `/player/1970288503/identity-cosmetics` | 200 | player, summary, names, name_changes, skins |
| GET | `/player/1970288503/punishments` | 200 | player_uid, punishments, updated_at |
| GET | `/heroes/stats?season=20` | 200 | season, ban_matches, ban_slots_per_match, bans, heroes, maps, teamups, timestamp |
| GET | `/hero-stats-history/1016?days=30&platform=pc` | 200 | hero_id, rank, platform, data |
| GET | `/hero-players/1016?device=1&season=20` | 200 | _id, players, timestamp |
| GET | `/hero-matchups` | 200 | 1024, 1025, 1022, 1053, 1055, 1031, 1054, 1023, 1037, 10572, 1041, 1038, 1020, 1043, 1014, 1050, 1027, 1052, 1018, 1058, 1060, 1067, 1035, 1042, 1047, 1036, 1046, 1044, 1059, 1061, 1064, 1040, 1029, 1051, 10571, 1034, 1065, 1049, 1016, 1030, 1062, 1045, 1011, 1033, 1039, 1048, 1063, 1066, 1026, 1056, 1017, 1032, 1028, 1021, 10573, 1015 |
| GET | `/hero-skins` | 200 | _id, data, timestamp |
| GET | `/roles/data` | 200 | array (9 rows) |
| GET | `/rank-distribution/data` | 200 | array (23 rows) |
| GET | `/leaderboard/data?device=1&season=last` | 200 | timestamp, players, device, season |
| POST | `/find-player` | 200 | array (10 rows) |

POST `/find-player` is a read-only search, tested with JSON `{"name":"GS-"}`. Search can return multiple candidates; it is not an exact-name identity guarantee.

## Other verified reads

- `GET /player-match-history/{uid}?skip=0&game_mode_id=3&hero_id=0&season=20`: Custom history; JSON array. Advance `skip` by 20; stop on empty results. Zero is the frontend unfiltered mode/hero selector.
- `GET /matches/{match_uid}`: full completed match, all players and per-hero K/D/A/playtime. GS-4 example: `5517895_1790571442_1267080_11001_11`.

## Response contracts and meaning

- **Player:** `player`, `stats`, `visibility`, `career_settings`, `match_history`, `heroes_ranked`, `heroes_unranked`, `maps`, `teammates`, `matchups`. Visibility is split by overview/career/history/timeline. Hero rows include cumulative playtime, damage/healing/damage taken and MVP/SVP counts. Matchups are the player’s results against enemy heroes.
- **Rank history:** `summary`, `matches`, `transitions`, `season`, `player`. Summary includes starting/current/peak score, net score, largest gain/loss and promotion/demotion counts. Match rows include timestamp, match ID, hero, win, score and level before/after, score change; transitions identify promotions/demotions. Summary net score should be taken as supplied, not assumed to equal current minus starting without checking its scope.
- **Identity/cosmetics:** `summary`, `names`, `name_changes`, `skins`, `player`. Names include first/last detection, match counts and current flag. Changes include previous name, detection date and originating match. Skin rows include hero/skin IDs, matches/wins/losses, win rate, playtime, first/last played and seasons. These are observed usage records, not owned inventory.
- **Punishments:** historical array with ID/type/reason, issued time, duration and expiry plus `updated_at`. Reason codes are opaque unless independently decoded.
- **Global hero stats:** season/timestamp, rank buckets, hero matches/wins and mirror matches, ban counts/slots/denominators, hero-by-map matches/wins, team-ups and hero-pair variants. Existing non-mirror win rate is not a new feature; explicit mirror counts and historical season selectors are additions.
- **Hero history:** daily date, total matches, hero matches/wins, win/pick/ban rates; kills/deaths/assists/playtime, damage/healing/damage taken, KDA and per-minute combat values. Frontend scope is Celestial+ and platform `pc`/`console`, not arbitrary profile/page filters.
- **Hero players:** players with UID/name/platform/rank, matches/wins, K/D/A, playtime, damage/healing/damage taken, MVP/SVP. A hero leaderboard already exists in our client; this endpoint is an alternative source and adds fields.
- **Hero matchups:** hero A -> hero B -> matches/wins. Frontend presents enemy-team matchup win rates across ranks/platforms. Do not infer causal counters or apply the profile season filter to this fixed aggregate.
- **Hero skins:** per-hero total matches and per-skin match counts; supports usage share/popularity. Skin display metadata is in static assets.
- **Roles/data:** rank buckets containing composition strings such as `1,1,2,2,3,3`, matches and wins. This is team-role composition meta, different from a player’s role totals.
- **Rank distribution:** counts by rank; percentages/mean/median are frontend calculations over the tracked population, not necessarily all game players.

## Static catalogs

Public frontend hero catalog includes names/IDs/classes, descriptions, real/internal names, difficulty, gender, attack method, hero type, usability/new flags, movement/turn speed, health/shield/armor by form; active abilities, passives, key bindings, icons and ultimate/passive flags; team-up descriptions/anchors and active-season windows. Skin metadata supplies names/quality/assets. These were inspected in frontend JS, not a dedicated live endpoint.

## Refresh and caveats

- Frontend discovers `POST /update-player/{uid}`. It checks `status == "success"` and `last_update_request`, queues an update and applies a cooldown. We did not call this mutation; exact operational limits are not established.
- All routes in the tested table returned JSON without a login/API key. This observation is not a published rate-limit or availability guarantee.
- Hero history platform `1` returned 400; use `pc` (tested).
- Leaderboard `device=1&season=last` returned players. Numeric `season=20` returned null in another probe; profile season IDs cannot be assumed to work for leaderboard season selectors.
- Raw hero accuracy aggregates such as `session_hit_rate` may be summed values. Do not treat them directly as a percentage without inspecting denominator semantics.
- No live custom-game combat-stat endpoint was established.

## Evidence

Raw JSON: `dist/provider-api-audit/rt-api-responses.json`; frontend inventory: `rt-static-inventory.json`; downloaded public assets: `assets/`. Earlier match evidence: `dist/rivalstracker-research/`.
