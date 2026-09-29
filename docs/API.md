# RivalsData API inventory

This is an observed inventory of the public web client's API, gathered by
reviewing the RivalsData UI and its browser requests on 2026-09-29. The upstream
API is undocumented and can change. Field sets below are examples from live
responses, not schemas guaranteed by RivalsData. The client converts every
implemented route to endpoint-specific model and row classes (such as `Match`,
`Character`, `PlayerSummary`, `ProficiencyResponse`, and `PunishmentsPage`).
Known fields are annotated; unknown keys remain accessible through `DataModel`
and `.raw` so upstream additions are not discarded.

## Implemented public read endpoints

| Site section | HTTP endpoint | Parameters sent by this client | Observed response |
| --- | --- | --- | --- |
| Search | `POST /players/search` | `{"name": name}` | Search rows; `aid` may contain the numeric UID after the final `_`. |
| Player overview | `POST /player` | `{"uid": number}` | Object keys observed: `cached_at`, `claimed`, `faction`, `icon`, `last_seen`, `leaderboard`, `level`, `login_os`, `match_history_is_visible`, `mood`, `name`, `rank_game_season`, `status`, `uid`, `xp`. `rank_game_season` is keyed by game/season ids; competitive rows include `battle_count`, `rank_game_id`, `rank_score`, and `win_count`. |
| Player live game | `POST /live` | `{"match_id": status.battle_id, "uid": number}` | Object keys observed: `players` (12 player entries keyed by team slot) and `team_avg_rank` (rank averages keyed by side). Player rows include `ai`, `games`, `icon`, `losses`, `name`, `proficiency`, `rank`, `side`, `team_id`, `top_heroes`, `uid`, and `wins`. The match ID comes from the player's current `/player` response; the endpoint was observed on a profile marked `In game (Competitive)`. |
| Player hero summary | `POST /player/heroes` | `uid`, optional `season`; wrapper `season="all"` sends season ID `-1` | Array rows: `assists`, `deaths`, `games`, `hero_id`, `kda`, `kills`, `losses`, `rank`, `wins`. The all-seasons selector was verified against the public `GS-` profile; `season=-1` returned 40 hero rows, while `season=0` returned none. |
| Player crosshairs | `POST /player/crosshairs` | `uid` | Array rows: `crosshair`, `uses`. |
| Player match history | `POST /player/matches/cached` (or `/player/matches`) | `uid`, `cursor`, optional `season`; cached endpoint also accepts `mode`, `hero`, `teammate` | Cached response keys observed: `matches`, `next_cursor`, `source`; match rows include `assists`, `deaths`, `game_mode_id`, `game_play_mode_id`, `hero_id`, `is_mvp`, `is_svp`, `is_win`, `kills`, `map_id`, `match_uid`, `os`, `placement`, `platform`, `rank_level`, `rank_score`, `score_change`, `season`, `team_score`, `timestamp`, `winner_camp`. A sample profile marked its history private; a private profile can return no visible match rows. |
| Player teammates | `POST /player/teammates` | `uid`, optional `season`, `mode` | Array rows: `games`, `icon`, `losses`, `name`, `teammate_uid`, `wins`. |
| Player proficiency | `POST /player/proficiency` | `uid` | Object keyed by account id (sample: `11001_{uid}`); each account has `hero_proficiency_infos` keyed by hero id, with `proficiency_level` and `proficiency_point`. |
| Player hero stats | `POST /player/stats/heroes` | `uid`, optional `season` | Array rows: `competitive`, `hero_id`, `quickplay`, `rank`. Each mode includes games, wins/losses, KDA, MVP/SVP counts, accuracy, and `per_10`/`per_game` combat averages. |
| Player map stats | `POST /player/stats/maps` | `uid`, optional `season` | Array rows: `map`, `competitive`, `quickplay`; each mode has games, wins, losses, winrate. |
| Player ban stats | `POST /player/stats/bans` | `uid`, optional `season` | Array rows: `hero_id`, `matches`, `wins`, `losses`, `winrate`. |
| Player punishments | `POST /player/punishments` | `uid` | Object keys: `chat`, `login`, `rank`; non-null entries include `expire`, `name`, `reason`, `time`, `uid`. |
| Player name history | `POST /player/name-history` | `uid` | Array rows: `first_seen`, `name`. |
| Global leaderboard | `GET /leaderboards` | `limit`, optional `skip`, `season`, `os` (Python `platform`) | Object keys observed: `count`, `players`, `updated_at`; row keys: `heroes`, `icon`, `losses`, `name`, `os`, `position`, `rank_level`, `rank_score`, `season`, `status`, `uid`, `wins`. |
| Hero tier list | `GET /stats/tierlist` | `platform`, `rank` | Object: `last_update`, `heroes`; rows include hero id, picks/bans, total games, winrate, pick rate, ban rate, and score. |
| Hero detail | `GET /stats/heroes/{hero_id}` | Path parameter | Object: `hero`, `last_update`, `season`; `hero` contains aggregate per-10 stats and pick/ban rates. |
| Hero trend/meta | `GET /stats/meta/{hero_id}` | `range` as `30d`, `90d`, or `180d` | Object: `hero_id`, `last_update`, `points`, `range`, `window_days`; point rows include timestamp, games, pick/ban rates, and winrate without mirror matches. |
| Hero leaderboard | `GET /stats/leaderboards` | `hero` plus caller-supplied query filters | Object: `last_update`, `players`; rows include combat averages, placement, score, rank, and wins/losses. |
| Team-up stats | `GET /stats/teamups` | `platform`, `rank`, optional `hero` | Object: `last_update`, `heroes`, where `heroes` maps hero ids to slot ids and rows with `bond_id`, `games`, `nm_winrate`, `pickrate`, `winrate`. |
| Punishments log | `GET /stats/punishments` | `kind`, optional `cursor` | Object: `last_update`, `next`, `results`; sample row keys: `expires_at`, `icon`, `issued_at`, `kind`, `name`, `peak_rank_level`, `peak_rank_score`, `rank`, `reason`, `uid`. |
| XP leaderboard | `GET /stats/xp` | Optional `cursor` | Object: `last_update`, `next`, `results`; sample row keys: `icon`, `name`, `rank`, `uid`, `xp`. |
| Top 500 finishes | `GET /stats/oaa` | `os` (Python `platform`) | Object: `count`, `last_update`, `os`, `players`; sample row keys: `avg_placement`, `avg_score`, `finishes`, `icon`, `name`, `seasons`, `uid`. |
| Hero comm-ban insight | `GET /stats/commbans` | `mode` (`all` or `competitive`) | Object: `heroes`, `last_update`, `mode`, `overall_pct`; hero rows: `ci95`, `hero_id`, `pct`, `qualifying_players`, `vs_avg`, `weighted_banned`, `weighted_players`. |
| Hero AFK insight | `GET /stats/leavers` | `mode` (`all` or `competitive`) | Object: `heroes`, `last_update`, `mode`, `overall_pct`; hero rows: `ci95`, `games`, `hero_id`, `leaves`, `leaves_per_player`, `pct`, `players`, `vs_avg`. |
| Faction details | `GET /faction/{faction_id}` | Path parameter | Faction `captain`, `description`, `members`, `name`, `region`, `results`, `tag`, `type`; member records contain account id, config/rank, game status, and name. |
| Match details | `POST /match` | `{"match_id": "..."}` | Object keys observed: `match_uid`, `replay_id`, `winner_camp`, `duration_seconds`, `map_id`, `game_mode_id`, `game_play_mode_id`, `platform`, `timestamp`, `draft`, `teams`; team player rows include combat stats and per-hero usage. |
| Public profile card | `GET /profiles/{uid}` | Numeric UID path parameter; `Profiles.get` resolves usernames | Object: `leaderboard_social`, `socials`, `uid`, `updated_at`. |
| Favorites lookup | `POST /favorites` | `{"uids": [numeric_uid, ...]}` | Array of public player summaries with `aid`, `config_server`, `games`, `name`, and `status`. |

The client exposes these read resources through `RivalsDataClient` and `Player`;
see README examples and method docstrings. `DataModel.win_rate` returns an
integer percentage from a direct win-rate field, `wins`/`losses`, or the
competitive profile row's `win_count`/`battle_count`. If the source provides
none of these, it returns `None`.

## Observed UI and routes

| UI route | What the UI exposes |
| --- | --- |
| `/` | Search, top leaderboard, favorites, top heroes, and top team-ups. |
| `/leaderboard` | Name filter, online-only switch, platform, season, refresh, and player rows. |
| `/stats` | Hero tier list with rank/platform/role filters and tier/win/pick/ban/games sorting. |
| `/team-ups` | Team-up pairings with hero, rank, and platform filters. |
| `/insights/punishments`, `/insights/xp`, `/insights/oaa`, `/insights/toxicity`, `/insights/afk` | Punishment log, XP ranking, Top 500 finishes, hero comm-ban rate, and hero AFK rate. |
| `/player/{uid}` | Overview, hero summaries, teammates, crosshairs, Match History, Live Game, Proficiency, Stats, Punishments, and Name History tabs. Match History may be private. |
| `/heroes/{slug}/stats` | Hero statistics and selectable 30/90/180-day charts. |
| `/heroes/{slug}/leaderboard` | Hero-specific ranked players. |
| `/heroes/{slug}/counters` and `/heroes/{slug}/synergy` | The UI displayed “Coming Soon” during inspection; no public data call was observed. |
| `/factions/{faction_id}` | Faction description and members. |
| `/matches/{match_id}` | Match detail route linked from an expanded public match-history card. |
| `/profiles` | Account-facing profile management page. |

The Live Game tab requests `POST /live` for profiles whose `status.battle_id`
is set. The client exposes this as `player.live_game.fetch()`. Since game status
can change, load a fresh player profile before fetching; the method returns
`None` when that profile has no active battle ID.

## Account actions and unresolved endpoints

Frontend assets also reference `GET /profiles`, `POST /profiles/{username}/edit`,
`POST /bind/start`, and `POST /bind/check`. These are associated with profile
management and account linking. Their complete request/response contracts and
authentication behavior were not established. Profile edit and bind routes
can modify account state; they are documented here for completeness but are
not implemented as public methods. `GET /profiles/{username}` and
`POST /favorites` have thin read wrappers, but their response schemas remain
unverified.

Other open research items:

- Capture response bodies for the remaining Insights mode/filter variants.
- Verify the hero leaderboard query parameters and faction response shape from
  real visible links.
- Determine whether match-history cursor pagination and the uncached route
  remain available for accounts that have made history public.
- Recheck this inventory when the site changes. Do not infer a supported API
  contract from a route string alone.
