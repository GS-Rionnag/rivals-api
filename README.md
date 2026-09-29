# rivalsdata-api

An unofficial Python client for RivalsData's public Marvel Rivals data. It
uses the site's undocumented API, so routes and fields can change. The client
keeps unknown response fields accessible instead of discarding them.

## Install

Python 3.10 or newer:

```console
python -m pip install rivalsdata-api
```

For editable development, clone the repository and run
`python -m pip install -e '.[dev]'`. The optional Camoufox Cloudflare fallback
is installed with `python -m pip install 'rivalsdata-api[browser]'`, followed
by `python -m camoufox fetch`.

## Quick start

```python
from rivalsdata import RivalsDataClient

with RivalsDataClient() as rd:
    player = rd.get_player("GS-")  # numeric UID works too
    print(player.name, player.level, player.rank_game_season)

    # Player profile sections are lazy resource managers.
    hero_season = player.heroes.fetch(season=20)
    map_stats = player.stats.maps(season=20)
    match_page = player.matches.fetch(season=20)

    # Site-wide resources are available from the client.
    leaderboard = rd.leaderboards.fetch(limit=100, season=20, platform=1)
    tier_list = rd.heroes.tier_list(platform=1, rank="grandmaster_plus")
    team_ups = rd.team_ups.fetch(platform=1, rank="grandmaster_plus")
    xp_page = rd.insights.xp()

print(hero_season[0].win_rate)  # integer percent when wins/losses are present
```

`Player` and returned `DataModel` objects support both mapping access and
attribute access (`player["level"]` or `player.level`). Nested dictionaries
and arrays are wrapped recursively; `.raw` returns a shallow copy of a model's
original JSON. For endpoints whose fields evolve, these generic typed wrappers
preserve the complete payload.

## Public resources

- `rd.leaderboards.fetch(...)` — global player ranking.
- `rd.heroes.tier_list(...)`, `.get(hero_id)`, `.meta(hero_id, range=90)`,
  `.leaderboard(hero_id, **filters)` — hero metrics and ranking.
- `rd.team_ups.fetch(...)` — team-up stats.
- `rd.insights.punishments(...)`, `.xp(...)`, `.top_500(...)`, `.commbans(...)`,
  `.leavers(...)` — public insights and cursor metadata.
- `rd.factions.get(faction_id)`, `rd.matches.get(match_id)`,
  `rd.profiles.get(username)`, and `rd.favorites.fetch(uids)` — detail/profile
  lookups.
- `player.heroes.fetch(...)`, `.matches.fetch(...)`, `.teammates.fetch(...)`,
  `.crosshairs.fetch()`, `.proficiency.fetch()`, `.punishments.fetch()`,
  `.name_history.fetch()` — profile sections.
- `player.stats.heroes(...)`, `.maps(...)`, `.bans(...)` — detailed profile stats.

See [the observed API inventory](docs/API.md) for methods, parameters, observed
response shapes, and endpoints that require a RivalsData account. The API
inventory distinguishes observed behavior from inferred/unverified details.

## Cloudflare fallback

Requests use curl_cffi with a Chrome TLS profile by default. If blocked, enable
the optional browser fallback:

```python
with RivalsDataClient(use_browser_fallback=True) as rd:
    player = rd.get_player(1970288503)
```

## Errors and contributions

All package exceptions inherit from `RivalsDataError`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, code layout, change workflow, and
notes for new contributors. [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
is the handoff document for new coding sessions.

This project is not affiliated with RivalsData, NetEase, or Marvel. Keep
request rates reasonable and respect the site's terms.
