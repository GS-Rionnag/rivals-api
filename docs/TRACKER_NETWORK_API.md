# Tracker.gg Marvel Rivals API audit

Verified 2026-10-01 using this project’s Camoufox browser. Base: `https://api.tracker.gg`. Browser-facing undocumented routes are distinct from any supported developer API. No API key or signed-in account was used for the successful public reads. Direct non-browser requests encountered 403; browser requests succeeded. No cookies/tokens are stored in these research notes.

## Exact observed requests

| Method | URL | HTTP |
|---|---|---|
| GET | `/api/v2/marvel-rivals/standard/profile/ign/GS-?` | 200 |
| GET | `/api/v2/marvel-rivals/standard/matches/ign/GS-/live?` | 200 |
| GET | `/api/v2/marvel-rivals/standard/profile/ign/GS-/segments/career?mode=all&season=20` | 200 |
| GET | `/api/v1/marvel-rivals/crosshairs?platformUserIdentifier=GS-` | 200 |
| GET | `/api/v1/marvel-rivals/standard/leaderboards?&skip=0&take=100` | 400 |
| GET | `/api/v1/marvel-rivals/crosshairs?page=1&sort=upvotes&players=all` | 200 |
| GET | `/api/v1/marvel-rivals/lfg/search` | 200 |
| GET | `/api/v2/marvel-rivals/standard/matches/ign/Motel%207?` | 200 |
| GET | `/api/v2/marvel-rivals/standard/matches/5513426_1788985360_1245106_11001_12` | 200 |
| GET | `/api/v2/marvel-rivals/standard/profile/ign/GS-/aggregated?localOffset=240&filter=encounters&mode=all&season=20` | 200 |
| GET | `/api/v2/marvel-rivals/standard/profile/ign/GS-/stats/overview/ranked?season=20` | 200 |
| GET | `/api/v1/marvel-rivals/metadata/type/hero` | 200 |

## Additional routes verified in the preceding season comparison

- `GET /api/v2/marvel-rivals/standard/profile/ign/GS-/segments/career?mode=competitive&season=18` (also 19 and 20; `all` and `quick-match` tested).
- `GET /api/v2/marvel-rivals/standard/matches/ign/GS-?season=20&next=2` (seasons 18/19 also traversed).

## Response contracts

- **Profile:** wrapper `data`, then `platformInfo`, `userInfo`, `metadata`, `segments`. Metadata includes season catalog/current/default season, supported modes, privacy flags and other profile context. Stats carry raw value, display value/type/category, display name and sometimes percentile. `ign` is the observed platform slug, not a numeric game UID. Encode names in URLs; do not confuse Tracker’s UUID account ID with the game UID.
- **Career:** wrapper `data` array containing `overview`, `ranked-peaks`, `hero`, `hero-role` segments. Select `mode` and `season`. Hero participation counts can be fractional; they are not necessarily unique completed games. An empty Quick Match segment was observed even when history had quick-play matches.
- **Rank stat history:** `data.history` holds timestamp/stat tuples; stat value includes rank name and rating. `leaderboard`, `expiryDate`, `bestMatches` also exist. In the tested ranked request `leaderboard` and `bestMatches` were null, so best-match content is not verified.
- **Matches:** `data.matches` with attributes, metadata and player summaries; `data.metadata.next` supplies pagination. Use returned `next`, not invented `page` parameters. In prior traversal, later pages crossed into earlier seasons despite `season`; filter each match’s season if an exact season count is needed.
- **Full match:** `attributes`, `metadata`, `segments`. Player segment stats include K/D/A, damage/healing/damage taken, per-minute values, last/head/solo kills, hit rates, kill streaks/multikills, attacks/hits, shield/summoner/chaos hits and hero-specific features. Hero segments identify account ID plus hero ID and carry per-hero stats/playtime. Metadata includes map name/mode/image, scores, teams, replay, bans, timestamps, bot/MVP/SVP/party information and completeness flags.
- **Encounters:** `data.offset`, `heatmaps`, `teammates`, `enemies`, `parties`. Query `filter=encounters`, `mode=all`, `season=20`, `localOffset=240` returned both teammate and opponent rows. Rows have platform info, last match timestamp, encounter matches/KD/win%, plus other player’s season rank/win%/KD/matches. Existing client teammates are a partial equivalent. Frontend warns unseasoned encounter scope is last 75 days. `heatmaps` was null for this filtered request; no heatmap functionality is confirmed.
- **Crosshairs:** `data` array, frontend page size 20. Gallery query supports page/sort/players/search; profile query supports platformUserIdentifier/userId. Rows contain ID, name, game code, score, dates, hero ID, author/account/pro/rank/user-vote fields (some null). GS- profile query returned an empty array; gallery returned populated data. Preview/settings parsing is frontend work.
- **LFG:** `data` array with player/user info, comments, metadata (region/platform/playlist/roles/language/mic/timezone), rank feature stat, MVP/KDA/win stats, posting and expiry times. UI says posts expire after 48 hours. Search filters are assembled into query parameters; arrays become comma-separated. Read succeeded without login. Posting/contact actions were not tested.
- **Hero metadata:** `data.items` includes type/key/locale/name/description/image/role key and name.

## Exact advanced-stat fields captured

- **Career / overview:** `timePlayed`, `matchesPlayed`, `matchesWon`, `matchesWinPct`, `kills`, `deaths`, `assists`, `kdRatio`, `kdaRatio`, `totalHeroDamage`, `totalHeroDamagePerMinute`, `totalHeroHeal`, `totalHeroHealPerMinute`, `totalDamageTaken`, `totalDamageTakenPerMinute`, `lastKills`, `headKills`, `soloKills`, `maxSurvivalKills`, `maxContinueKills`, `continueKills3`, `continueKills4`, `continueKills5`, `continueKills6`, `mainAttacks`, `mainAttackHits`, `shieldHits`, `summonerHits`, `chaosHits`, `totalMvp`, `totalMvpPct`, `totalSvp`, `totalSvpPct`, `ranked`, `peakRanked`.
- **Career / ranked-peaks:** `peakTiers`, `lifetimePeakRanked`.
- **Career / hero:** `timePlayed`, `timePlayedWon`, `matchesPlayed`, `matchesWon`, `matchesWinPct`, `kills`, `deaths`, `assists`, `kdRatio`, `kdaRatio`, `totalHeroDamage`, `totalHeroDamagePerMinute`, `totalHeroHeal`, `totalHeroHealPerMinute`, `totalDamageTaken`, `totalDamageTakenPerMinute`, `lastKills`, `headKills`, `soloKills`, `survivalKills`, `continueKills`, `continueKills3`, `continueKills4`, `continueKills5`, `continueKills6`, `mainAttacks`, `mainAttackHits`, `shieldHits`, `summonerHits`, `chaosHits`, `totalMvp`, `totalSvp`, `featureNormalData1`, `featureNormalData2`, `featureNormalData3`, `featureNormalData4`, `featureCriticalRate1CritHits`, `featureCriticalRate1Hits`, `featureCriticalRate2CritHits`, `featureCriticalRate2Hits`, `featureHitRate1UseCount`, `featureHitRate1RealHitHeroCount`, `featureHitRate1ChaosHits`, `featureHitRate1AllyHits`, `featureHitRate1HeroHits`, `featureHitRate1EnemyHits`, `featureHitRate1ShieldHits`, `featureHitRate1SummonerHits`, `featureHitRate2UseCount`, `featureHitRate2RealHitHeroCount`, `featureHitRate2ChaosHits`, `featureHitRate2AllyHits`, `featureHitRate2HeroHits`, `featureHitRate2EnemyHits`, `featureHitRate2ShieldHits`, `featureHitRate2SummonerHits`, `featureSpecialData1Total`, `featureSpecialData1Value`, `proficiencyLevel`, `proficiencyPoints`.
- **Career / hero-role:** `timePlayed`, `timePlayedWon`, `matchesPlayed`, `matchesWon`, `matchesWinPct`, `kills`, `deaths`, `assists`, `kdRatio`, `kdaRatio`, `totalHeroDamage`, `totalHeroDamagePerMinute`, `totalHeroHeal`, `totalHeroHealPerMinute`, `totalDamageTaken`, `totalDamageTakenPerMinute`, `lastKills`, `headKills`, `soloKills`, `survivalKills`, `continueKills`, `continueKills3`, `continueKills4`, `continueKills5`, `continueKills6`, `mainAttacks`, `mainAttackHits`, `shieldHits`, `summonerHits`, `chaosHits`, `totalMvp`, `totalSvp`.
- **Full match / player:** `timePlayed`, `kills`, `deaths`, `assists`, `kdRatio`, `kdaRatio`, `totalHeroDamage`, `totalHeroDamagePerMinute`, `totalHeroHeal`, `totalHeroHealPerMinute`, `totalDamageTaken`, `totalDamageTakenPerMinute`, `lastKills`, `headKills`, `soloKills`, `sessionHitRate`, `maxSurvivalKills`, `maxContinueKills`, `maxContinueWins`, `continueKills3`, `continueKills4`, `continueKills5`, `continueKills6`, `mainAttacks`, `mainAttackHits`, `shieldHits`, `summonerHits`, `chaosHits`, `heroSessionHitRate`, `heroMainAttacks`, `heroMainAttackHits`, `heroShieldHits`, `heroSummonerHits`, `heroChaosHits`, `featureNormalData1`, `featureNormalData2`, `featureNormalData3`, `featureNormalData4`, `featureCriticalRate1CritHits`, `featureCriticalRate1Hits`, `featureCriticalRate2CritHits`, `featureCriticalRate2Hits`, `featureHitRate1UseCount`, `featureHitRate1RealHitHeroCount`, `featureHitRate1ChaosHits`, `featureHitRate1AllyHits`, `featureHitRate1HeroHits`, `featureHitRate1EnemyHits`, `featureHitRate1ShieldHits`, `featureHitRate1SummonerHits`, `featureHitRate2UseCount`, `featureHitRate2RealHitHeroCount`, `featureHitRate2ChaosHits`, `featureHitRate2AllyHits`, `featureHitRate2HeroHits`, `featureHitRate2EnemyHits`, `featureHitRate2ShieldHits`, `featureHitRate2SummonerHits`, `featureSpecialData1Total`, `featureSpecialData1Value`, `ranked`.
- **Full match / hero:** `timePlayed`, `kills`, `deaths`, `assists`, `kdRatio`, `kdaRatio`, `totalHeroDamage`, `totalHeroDamagePerMinute`, `totalHeroHeal`, `totalHeroHealPerMinute`, `totalDamageTaken`, `totalDamageTakenPerMinute`, `lastKills`, `headKills`, `soloKills`, `sessionHitRate`, `sessionSurvivalKills`, `sessionContinueKills`, `continueKills3`, `continueKills4`, `continueKills5`, `continueKills6`, `mainAttacks`, `mainAttackHits`, `shieldHits`, `summonerHits`, `chaosHits`, `featureNormalData1`, `featureNormalData2`, `featureNormalData3`, `featureNormalData4`, `featureCriticalRate1CritHits`, `featureCriticalRate1Hits`, `featureCriticalRate2CritHits`, `featureCriticalRate2Hits`, `featureHitRate1UseCount`, `featureHitRate1RealHitHeroCount`, `featureHitRate1ChaosHits`, `featureHitRate1AllyHits`, `featureHitRate1HeroHits`, `featureHitRate1EnemyHits`, `featureHitRate1ShieldHits`, `featureHitRate1SummonerHits`, `featureHitRate2UseCount`, `featureHitRate2RealHitHeroCount`, `featureHitRate2ChaosHits`, `featureHitRate2AllyHits`, `featureHitRate2HeroHits`, `featureHitRate2EnemyHits`, `featureHitRate2ShieldHits`, `featureHitRate2SummonerHits`, `featureSpecialData1Total`, `featureSpecialData1Value`.

Opaque `featureNormalData*`, `featureHitRate*`, `featureCriticalRate*`, `featureSpecialData*` require hero-specific display definitions. We confirmed fields, not universal meanings. Zero/null fields alone do not establish a useful statistic.

## Discovered routes and product features not successfully exercised

- `GET /api/v1/marvel-rivals/crosshairs/id/{id}`: static client route; not tested.
- `POST /api/v1/marvel-rivals/crosshairs`, `PUT /api/v1/marvel-rivals/crosshairs`, `DELETE /api/v1/marvel-rivals/crosshairs/{id}`, `POST .../upvote/{id}`, `POST .../downvote/{id}`: frontend sends account Bearer authorization. No write/vote/delete action performed. Payload schemas not fully verified.
- `/api/v1/marvel-rivals/standard/leaderboards?&skip=0&take=100` was observed but returned 400. Generic client accepts arbitrary selector query fields; valid Marvel Rivals ranked selectors were not established. Do not advertise it as a working leaderboard route.
- Custom leaderboards, Rank Me polls/play/leaderboard, profile claiming/customization, Premium, OBS overlays and desktop/mobile apps are public UI/config features, not proven anonymous stats API capabilities.
- Shared generic Tracker code includes session and other routes for multiple games. Their presence is not proof that Marvel Rivals supports them.

## Data and operational caveats

- Profile `lastUpdated` carried an implausible sentinel date in prior evidence; use credible provider timestamps and report uncertainty.
- Match summary/full detail disagreed on GS- assists (12 vs 1) for `5513426_1788985360_1245106_11001_12`. RivalsData and RivalsTracker agreed with the full detail. Prefer completed detail but preserve the discrepancy.
- GS- S10 ranked matches differed across sources (RivalsData 79, the others 77). Hero playtime also differed materially. Provider coverage/refresh/definitions must remain visible.
- Tracker labels `totalDamageTaken` as “Damage Blocked.” Retain raw field/source label; semantic equivalence with RivalsData blocked or game damage taken is not established.
- Inactive live request returned `{}`; active payload and live custom combat stats are unverified. Desktop hero-swap alerts and video clips are advertised app features, not established REST outputs.
- No published rate limits/authenticated private contracts were learned from these probes.

## Evidence

Public response bodies: `dist/provider-api-audit/tracker-network.json`, `tracker-extra.json`; eleven page snapshots: `tracker-ui.json`; 195 downloaded frontend JS assets: `tracker-assets/`. Earlier season/match captures: `dist/gs-season-comparison/`. Source pages: [GS-](https://tracker.gg/marvel-rivals/profile/ign/GS-/), [Crosshairs](https://tracker.gg/marvel-rivals/crosshairs), [LFG](https://tracker.gg/marvel-rivals/lfg), [desktop features](https://tracker.gg/marvel-rivals/app).
