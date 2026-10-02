# Player search: `silo` and `siloء`

Live checks on 2026-10-02. The requested behavior is a list of accounts for
`silo` that includes `siloء`, whose final character is U+0621 (Arabic hamza).
The exact-name result identifies that account as game UID **283622404**.

## Results

| Source | Search for `silo` | Search for `siloء` | Meets the requested suggestion behavior now? |
|---|---|---|---|
| RivalsData | One result: `Silo`, UID 1254981449 | One result: `siloء`, UID 283622404 | No |
| RivalsTracker | 10 results; `siloء` is fifth, UID 283622404 | One result: `siloء`, UID 283622404 | Yes |
| RivalsMeta | 10 results; `siloء` is fifth, UID 283622404 | One result: `siloء`, UID 283622404 | Yes |
| Tracker.gg autocomplete | 20 results, excluding `siloء` | One result: `siloء` | No for the shorter query |
| Tracker.gg submitted search | One result: `Silo` | One result: `siloء` | No for the shorter query |
| OP.GG website | Five displayed results after loading; `siloء` is fifth | Navigates to the `siloء` profile | Yes at the website level; a reusable search API contract was not established |

RivalsTracker and RivalsMeta returned identical search arrays in these checks.
This does not establish that they have independent databases or search coverage.
Tracker.gg's exact-name profile route also returned a public overview response
for `siloء`. These observations show that the character can be represented and
the account can be found. They do not establish why the short-query suggestions
omit it, nor that special characters in general are filtered out.

RivalsTracker's observed list, in order:

1. `-SILO_`
2. `Silo`
3. `Silo_`
4. `Silo_RAE`
5. `siloء`
6. `Silo_Koios`
7. `Silo af`
8. `Silo.is.bot`
9. `silo_greedy`
10. `Silo_92`

## Exact requests and evidence

- RivalsData: `POST https://api.rivalsdata.com/players/search`, JSON
  `{"name":"silo"}` or `{"name":"siloء"}`. Both returned HTTP 200.
  The friend's record contains `aid: "11001_283622404"`.
- RivalsTracker: `POST https://api.rivalstracker.com/api/find-player`, same JSON
  bodies. Both returned HTTP 200. The friend's row was
  `{"aid":"283622404","name":"siloء","cur_head_icon_id":"31048204"}`.
- RivalsMeta: `POST https://rivalsmeta.com/api/find-player`, same JSON bodies.
  Both returned HTTP 200 and the same search rows as RivalsTracker. This route
  and body were found in the site's current search component and runtime config.
- Tracker.gg: `GET https://api.tracker.gg/api/v2/marvel-rivals/standard/search`
  with `platform=ign`, `query=silo` or `query=siloء`, and `autocomplete=true`
  for suggestions. Submitted search omits `autocomplete`. Direct HTTP was
  challenged with 403; the existing Camoufox provider fallback succeeded for
  all four searches. Exact profile:
  `/api/v2/marvel-rivals/standard/profile/ign/silo%D8%A1`.
- OP.GG: [short-name search](https://op.gg/marvel-rivals/search/silo) and
  [full-name search](https://op.gg/marvel-rivals/search/silo%D8%A1), checked in
  Camoufox. The short-name page initially showed four rows; after a longer load
  it showed `Silofael`, `Silonace`, `silosue`, `Siloger`, and `siloء`. The exact
  search opened the profile, which showed privacy and update notices. Those
  notices were respected; no update button was clicked and no private stats
  were requested. The list itself is the relevant evidence here.

All these are observed website behaviors, not permanent API guarantees.
Local raw responses and browser observations are saved in the ignored
`dist/search-audit/` directory. No cookies, authorization headers, or API keys
were saved in the research artifacts.

## Existing wrapper behavior

The Python method `RivalsClient.search_players()` already uses RivalsTracker's
multi-result `/find-player` endpoint. A live call to `search_players("silo")`
returned all 10 candidates, preserving `siloء` and adding numeric UID 283622404.
It currently queries RivalsTracker alone; it does not merge all three providers.

```python
from rivals_api import RivalsClient

with RivalsClient() as client:
    candidates = client.search_players("silo")
    # Includes a row with name == "siloء" and uid == 283622404.
```

Following this audit, the MCP search/profile flow was updated:

| MCP tool | What it calls | Live result for `silo` |
|---|---|---|
| `search_players(name="silo")` | `client.search_players("silo")` | 10 candidates, including `siloء`, UID 283622404 |
| `search_player_candidates(name="silo")` | `client.search_players("silo")` | 10 candidates, including `siloء`, UID 283622404 |
| `get_player_profile(uid=283622404)` | `get_player("283622404")` | Profile overview for the selected numeric UID; not a candidate search |

The original MCP `search_players` resolved one account through RivalsData and
returned `Silo`, UID 1254981449. It now returns the same list as the candidate
tool. For a selection list, use **`search_players`**, then **`get_player_profile`**
with the chosen UID. The candidate tool remains a compatibility alias.
Entering `silo` into a single-account resolver should not be treated as a
selection of `siloء`.

## Other trackers and APIs checked

- [RivalCounter](https://www.rivalcounter.com/) routes player searches to
  filtering its top-500 leaderboard snapshot. Its frontend labels this as
  matching leaderboard entries. The current PC snapshot did not contain this
  UID; this is not a general player-discovery replacement.
- [MarvelRivalsAPI's documented search](https://docs.marvelrivalsapi.com/search-player-19312750e0)
  is `GET /api/v1/find-player/{username}` and documents one name/UID result and
  an `x-api-key` header. The anonymous `silo` probe returned a gateway error
  (502), so live account coverage was not established.
- [RivalsIsland](https://api.rivalsisland.com/) documents
  `GET /players/search?name=...` in `/docs/openapi.json`, with a singular
  `player` response. Both anonymous queries returned 401, missing API key.
  Its UI describes exact-name lookup; suggestion coverage is unverified.
- `mrapi.org` did not resolve in this environment. No current search behavior
  could be verified.

## Recommendation

Use the RivalsTracker candidate path for this task. RivalsMeta is a
confirmed alternative endpoint, and OP.GG also finds the account on its website.
An additional provider is not needed to produce the requested list today.

If “always included” is a product requirement, third-party suggestions alone
cannot guarantee it. Persist the user's verified association between the alias
`silo` and UID 283622404, then merge that known account with live suggestions,
deduplicating by UID and preserving the displayed name `siloء`. Keep aliases
scoped to the user or application that chose them; do not globally equate `Silo`
with `siloء`. Resolve future names through the stored UID when available, and
retain a clearly labeled saved candidate during upstream outages.

The follow-up MCP change routes `search_players` to the existing candidate
search and adds the UID-only profile tool. A persistent alias index is not
implemented.
