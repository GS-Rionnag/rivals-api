# rivals-api

**Marvel Rivals stats from three public sources, through one Python client.**

`rivals-api` brings together RivalsData, RivalsTracker, and Tracker.gg. Look up
players, explore matches and heroes, calculate win rates, or use the read-only
MCP server in an AI client. It is unofficial and requires Python 3.10+.

```text
RivalsData ────┐
RivalsTracker ─┼──► rivals-api ──► Python client / MCP tools / player dashboard
Tracker.gg ────┘
```

## Get started

```console
python -m pip install rivals-api
```

```python
from rivals_api import RivalsClient

with RivalsClient() as client:
    player = client.get_player("GS-")  # A player name or numeric UID
    rate = player.stats.win_rate()

    print(player.name, player.level)
    print(rate.wins, rate.games, rate.win_rate_pct)
    print(rate.metadata.coverage)
```

The default win rate is for the **current season**, combining Competitive and
Quickplay. If the current season cannot be verified, pass a season ID or
`season="all"`. The latter means all *available tracked history*, which may be
less than a player's lifetime history.

## What makes it useful

| Feature | Why it matters |
| --- | --- |
| **Three providers, one view** | Available data from RivalsData, RivalsTracker, and Tracker.gg can fill gaps when a source has less detail or fails. Match results retain source decisions in `provider_metadata`; win-rate results expose selections and provider errors in `metadata`. |
| **Win rates with evidence** | Normal calculations use win/loss counts rather than averaging provider percentages. Coverage and missing modes are reported, so an incomplete answer is recognizable. |
| **Match-verified rates** | `method="precise"` walks available match history and checks completed outcomes. Hero and class rates assign each match to the longest-played hero when the match details support it. Ambiguous matches stay unresolved. |
| **Persistent match cache** | Precise calculations retain history and details in SQLite. Later runs refresh recent pages and reuse verified older matches. |
| **Readable match data** | Maps, heroes, ranks, modes, platforms, and seasons have names alongside their original IDs. Models also preserve the source payload in `.raw`. |
| **AI-ready access** | Read-only MCP tools cover player profiles, matches, leaderboards, heroes, and more. `show_player_dashboard` can display a player card with a live match, hero form, or recent matches. |

### Pick the stats you need

```python
from rivals_api import RivalsClient

with RivalsClient() as client:
    player = client.get_player("GS-")

    ranked = player.stats.win_rate(mode="competitive")
    quickplay = player.stats.win_rate(mode="quickplay")
    heroes = player.stats.hero_win_rates(season="all")
    classes = player.stats.class_win_rates()

    print(ranked.win_rate_pct, quickplay.win_rate_pct)
    print(heroes.metadata.coverage)
```

`mode` accepts `"competitive"`, `"quickplay"`, or `"all"` (the default).
`season` accepts a provider season ID, `"current"`, or `"all"`.
Hero and class results have their own coverage metadata.

### Go deeper with match-verified rates

```python
from rivals_api import RivalsClient

with RivalsClient() as client:
    player = client.get_player("GS-")
    rate = player.stats.win_rate(method="precise")
    hero_rates = player.stats.hero_win_rates(method="precise")

    print(rate.win_rate_pct, rate.metadata.coverage)
    print(hero_rates.metadata.unresolved)
```

The first precise run may fetch many history pages and match details. It checks
each provider's complete match record independently; it does not splice hero
playtime from different sources. Missing playtime, ties, conflicting outcomes,
and other uncertain records are reported as unresolved. See the
[advanced usage guide](docs/ADVANCED_USAGE.md) for attribution and cache details.

### Explore players and matches

```python
from rivals_api import RivalsClient

with RivalsClient() as client:
    candidates = client.search_players("silo")
    for candidate in candidates:
        print(candidate.name, candidate.uid)

    if candidates:
        player = client.get_player(candidates[0].uid)
        history = player.matches.fetch(limit=20)
        if history.matches:
            match = history.matches[0].get_details()
            print(match.map, match.game_mode, match.platform)
            print(match.provider_metadata.errors)

    leaderboard = client.leaderboards.fetch(limit=100)
    tier_list = client.heroes.tier_list()
```

Match history combines and deduplicates provider results. Details are fetched
when you ask for them. More resources include live games, teammates, team-ups,
hero metrics, proficiency, factions, and public insights. Browse the
[API inventory](docs/API.md) for the full list and observed response shapes.

## Use it with an MCP client

```console
python -m pip install "rivals-api[mcp]"
```

For a local Claude Desktop connection, add this to its configuration and point
`command` at the Python executable where you installed the package:

```json
{
  "mcpServers": {
    "rivals-api": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "rivals_api.mcp_server"]
    }
  }
}
```

On macOS/Linux, use the environment's `bin/python` path. For local HTTP
testing, run `uvicorn rivals_api.mcp_server:app --host 127.0.0.1 --port 8000`;
the endpoint is `/mcp`. The [advanced usage guide](docs/ADVANCED_USAGE.md#mcp-server-chatgpt-and-claude)
covers remote hosting and the player dashboard.

## More detail

- [Advanced usage and MCP setup](docs/ADVANCED_USAGE.md)
- [Provider selection and match details](docs/PROVIDER_INTEGRATION.md)
- [Readable game references](docs/GAME_REFERENCES.md)
- [Release notes and migration](docs/CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

`RivalsDataClient` and the `rivalsdata` import path remain available for older
projects. This project is not affiliated with RivalsData, RivalsTracker,
Tracker.gg, NetEase, or Marvel. Public data can be incomplete, private, or stale.
