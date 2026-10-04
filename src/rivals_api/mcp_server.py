"""Model Context Protocol server for public RivalsData data.

Install the optional MCP dependency with ``pip install 'rivals-api[mcp]'``.
The server is read-only and supports stdio (Claude Desktop/local clients) and
Streamable HTTP (ChatGPT and other remote MCP clients).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from html import escape
from typing import Any, Literal

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise ImportError(
        "The MCP server requires the optional dependency. Install it with "
        "`pip install 'rivals-api[mcp]'`."
    ) from exc

from mcp.types import (
    CallToolResult,
    EmbeddedResource,
    TextContent,
    TextResourceContents,
)
from mcp_ui_server import create_ui_resource

from .client import RivalsClient
from .hero_ids import hero_id, hero_name

mcp = FastMCP(
    "Rivals API",
    instructions=(
        "Read public Marvel Rivals player profiles, match history, leaderboards, "
        "hero statistics, team-ups, insights, factions, and match details from "
        "RivalsData, RivalsTracker and Tracker.gg, preserving source conflicts. "
        "New tools cover rank history, cosmetics, encounters and community data. "
        "These results come from unofficial, undocumented APIs "
        "and can change. Use search_players for a list of name matches, then "
        "get_player_profile with the selected numeric UID. Other tools accept "
        "a numeric player UID or exact in-game name; player "
        "match history may be private. All tools are read-only."
    ),
)

PLAYER_DASHBOARD_URI = "ui://rivals-api/player-dashboard"
MCP_APP_HTML_MIME_TYPE = "text/html;profile=mcp-app"
PLAYER_DASHBOARD_APP_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{margin:0;width:100%;height:100%;background:#0d0f12;color:#f0f1f3}
body{font:14px system-ui,-apple-system,Segoe UI,sans-serif}
iframe{display:block;border:0;width:100%;height:100%;min-height:600px}
#status{padding:18px;color:#a9adb6}</style></head><body>
<div id="status">Loading Rivals API dashboardâ€¦</div>
<script>
addEventListener('message', event => {
  const message = event.data;
  if (!message || message.method !== 'ui/notifications/tool-result') return;
  const html = message.params?.structuredContent?.html;
  if (typeof html !== 'string') {
    document.getElementById('status').textContent = 'Dashboard data was not included.';
    return;
  }
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.title = 'Marvel Rivals player dashboard';
  frame.srcdoc = html;
  document.body.replaceChildren(frame);
});
</script></body></html>"""


@mcp.resource(
    PLAYER_DASHBOARD_URI,
    name="Marvel Rivals player dashboard",
    description="Interactive UI for the show_player_dashboard tool.",
    mime_type=MCP_APP_HTML_MIME_TYPE,
)
def player_dashboard_app() -> str:
    """Return the static frame for the dashboard tool's rendered result."""
    return PLAYER_DASHBOARD_APP_HTML


def _plain(value: Any) -> Any:
    """Convert package mapping models into JSON-serializable MCP results."""
    if isinstance(value, Mapping):
        result = {str(key): _plain(item) for key, item in value.items()}
        for id_key, name_key in (("hero_id", "hero_name"), ("top_hero_id", "top_hero_name")):
            if id_key in result and name_key not in result:
                name = hero_name(result[id_key])
                if name:
                    result[name_key] = name
        return result
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _call(method: Any, *args: Any, **kwargs: Any) -> Any:
    browser_fallback = os.environ.get(
        "RIVALS_API_BROWSER_FALLBACK",
        os.environ.get("RIVALSDATA_BROWSER_FALLBACK", "true"),
    ).lower() in ("1", "true", "yes")
    with RivalsClient(use_browser_fallback=browser_fallback) as client:
        return _plain(method(client, *args, **kwargs))


@mcp.tool()
def search_players(name: str) -> list[dict[str, Any]]:
    """Return matching players with their names and numeric game UIDs.

    Returns candidates rather than choosing one account. Pass the selected
    candidate's uid to get_player_profile to fetch their profile overview.
    """
    return _call(lambda client, query: client.search_players(query), name)


@mcp.tool()
def get_player(uid_or_name: str) -> dict[str, Any]:
    """Get a public player overview by numeric UID or in-game name.

    The overview's overall win rate refers to the current competitive season
    (latest available season with usable counts), not all seasons combined.
    """
    def fetch(client: RivalsClient, value: str) -> dict:
        player = client.get_player(value)
        return {**player.to_dict(), "win_rate": player.win_rate}

    return _call(fetch, uid_or_name)


@mcp.tool()
def get_player_profile(uid: int) -> dict[str, Any]:
    """Get a public profile overview by the numeric UID from search_players.

    Includes rank, level, available profile fields, and current-season
    competitive win rate. Does not resolve a username or choose a candidate.
    """
    if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
        raise ValueError("uid must be a positive integer")
    return get_player(str(uid))


@mcp.tool()
def get_current_match(uid_or_name: str) -> Any:
    """Get a player's current live match if the provider exposes it.

    Fetches a fresh profile first, so this checks current in-game status rather
    than returning match history or the player's last completed match. Live
    Custom-game discovery is not supported.
    """
    def fetch(client: RivalsClient, value: str) -> Any:
        player = client.get_player(value)
        return player.live_game.fetch()
    return _call(fetch, uid_or_name)


@mcp.tool(meta={
    "ui": {"resourceUri": PLAYER_DASHBOARD_URI},
    # ChatGPT currently accepts this alias alongside the standard Apps key.
    "openai/outputTemplate": PLAYER_DASHBOARD_URI,
})
def show_player_dashboard(
    uid_or_name: str,
    section: Literal["live_match", "hero_form", "recent_matches"] = "live_match",
) -> CallToolResult:
    """Show a player card with one freshly fetched data section.

    Fetches a fresh profile and one data section. Provider enrichment may make
    additional requests. Call again with another section to retrieve more data without
    combining live-match, hero, and match-history pulls. MCP Apps hosts can
    render the returned dashboard resource; all values are escaped before HTML
    output.
    The competitive record and win rate are for the latest available season.
    """
    browser_fallback = os.environ.get(
        "RIVALS_API_BROWSER_FALLBACK",
        os.environ.get("RIVALSDATA_BROWSER_FALLBACK", "true"),
    ).lower() in ("1", "true", "yes")
    with RivalsClient(use_browser_fallback=browser_fallback) as client:
        player = client.get_player(uid_or_name)
        live = _plain(player.live_game.fetch()) if section == "live_match" else None
        hero_rows = _plain(player.heroes.fetch()) if section == "hero_form" else []
        history = _plain(player.matches.fetch(limit=5)) if section == "recent_matches" else {}

    player_name = str(player.get("name", uid_or_name))
    name = escape(player_name)
    uid = escape(str(player.get("uid", "")))
    level = escape(str(player.get("level", "â€”")))
    xp = escape(str(player.get("xp", "â€”")))
    rank_data = player.get("rank_game_season", {})
    rank_text = "Rank data unavailable"
    competitive_summary = ""
    if isinstance(rank_data, Mapping):
        rank_rows = [row for key, row in rank_data.items()
                     if str(key).startswith("1001") and isinstance(row, Mapping)]
        if rank_rows:
            current = max(rank_rows, key=lambda row: int(row.get("rank_game_id", 0) or 0))
            rank_text = escape(str(current.get("rank", current.get("rank_score", "Rank available"))))
            battles = int(current.get("battle_count", 0) or 0)
            wins = int(current.get("win_count", 0) or 0)
            summary = player.get("career_summary", {})
            if isinstance(summary, Mapping) and summary.get("season") == current.get("rank_game_id"):
                career = summary.get("competitive", {})
                if isinstance(career, Mapping):
                    battles = int(career.get("games", battles) or 0)
                    wins = int(career.get("wins", wins) or 0)
            rate = round(wins * 100 / battles) if battles else None
            score = current.get("rank_score")
            competitive_summary = (
                f'<div class="competitive-line">'
                f'<span>{battles:,} competitive games</span>'
                + (f'<span>{rate}% season win rate</span>' if rate is not None else "")
                + (f'<span>{escape(str(score))} RP</span>' if score is not None else "")
                + '</div>'
            )

    chart_rows = []
    if isinstance(hero_rows, list):
        ranked_heroes = sorted(
            (row for row in hero_rows if isinstance(row, Mapping)),
            key=lambda row: int(row.get("games", 0) or 0),
            reverse=True,
        )[:6]
        for row in ranked_heroes:
            wins = int(row.get("wins", 0) or 0)
            losses = int(row.get("losses", 0) or 0)
            games = int(row.get("games", wins + losses) or 0)
            total = wins + losses
            win_rate = round(wins * 100 / total) if total else 0
            hero_id_value = row.get("hero_id", "Unknown hero")
            hero = escape(str(row.get("hero_name") or hero_name(hero_id_value) or hero_id_value))
            chart_rows.append(
                f'<div class="hero-row"><div class="hero-label"><span>{hero}</span>'
                f'<b>{win_rate}%</b></div><div class="track"><i style="width:{win_rate}%"></i>'
                f'</div><small>{games} games</small></div>'
            )
    hero_chart = (
        '<section class="section"><div class="section-head"><div><h2>Hero form</h2>'
        '<p class="sub">Win rate across the most played heroes</p></div>'
        '<span class="section-tag">SEASON</span></div>'
        + ("".join(chart_rows) if chart_rows else
           '<p class="empty">No hero win/loss data is available for this player.</p>')
        + '</section>'
    ) if section == "hero_form" else ""

    match_rows = history.get("matches", []) if isinstance(history, Mapping) else []
    if not isinstance(match_rows, list):
        match_rows = []
    recent = [row for row in match_rows[:10] if isinstance(row, Mapping)]
    recent_wins = sum(1 for row in recent if row.get("is_win") is True)
    recent_kills = sum(int(row.get("kills", 0) or 0) for row in recent)
    recent_deaths = sum(int(row.get("deaths", 0) or 0) for row in recent)
    recent_assists = sum(int(row.get("assists", 0) or 0) for row in recent)
    recent_kda = (recent_kills + recent_assists) / max(recent_deaths, 1) if recent else 0
    form_marks = []
    for row in recent:
        did_win = row.get("is_win") is True
        outcome = "W" if did_win else "L"
        label = "Win" if did_win else "Loss"
        kills = escape(str(row.get("kills", 0)))
        deaths = escape(str(row.get("deaths", 0)))
        assists = escape(str(row.get("assists", 0)))
        form_marks.append(
            f'<span class="form-mark {"win" if did_win else "loss"}" '
            f'title="{label} Â· {kills}/{deaths}/{assists}" aria-label="{label}, '
            f'{kills} kills, {deaths} deaths, {assists} assists">{outcome}</span>'
        )
    recent_section = (
        '<section class="section"><div class="section-head"><div><h2>Recent run</h2>'
        '<p class="sub">Latest visible matches</p></div>'
        + (f'<span class="section-tag">{recent_wins}W Â· {len(recent) - recent_wins}L</span>' if recent else '')
        + '</div>'
        + (f'<div class="form-strip">{"".join(form_marks)}</div>'
           f'<div class="form-foot"><span>Last {len(recent)} games</span>'
           f'<span>{recent_kills} / {recent_deaths} / {recent_assists} K/D/A</span>'
           f'<span>{recent_kda:.2f} KDA</span></div>' if recent else
           '<p class="empty">No public match history is available for this player.</p>')
        + '</section>'
    ) if section == "recent_matches" else ""

    if section != "live_match":
        match_section = ""
    elif isinstance(live, Mapping):
        slots = live.get("players", {})
        teams: dict[str, list[str]] = {}
        if isinstance(slots, Mapping):
            for row in slots.values():
                if isinstance(row, Mapping):
                    player_name = escape(str(row.get("name", "Unknown player")))
                    team_id = str(row.get("side", row.get("team_id", "Unknown side")))
                    rank = escape(str(row.get("rank", "â€”")))
                    wins = escape(str(row.get("wins", "â€”")))
                    losses = escape(str(row.get("losses", "â€”")))
                    top_heroes = row.get("top_heroes", [])
                    hero_label = ""
                    if isinstance(top_heroes, list) and top_heroes:
                        hero_label = escape(", ".join(
                            hero_name(hero) or str(hero) for hero in top_heroes[:2]
                        ))
                    detail = f"Rank {rank} Â· {wins}W/{losses}L"
                    if hero_label:
                        detail += f" Â· {hero_label}"
                    teams.setdefault(team_id, []).append(
                        f'<li><span>{player_name}</span><small>{detail}</small></li>'
                    )
        side_keys = sorted(teams)
        team_sections = []
        for index, team_id in enumerate(side_keys):
            avg_rank = live.get("team_avg_rank", {})
            avg = avg_rank.get(team_id) if isinstance(avg_rank, Mapping) else None
            avg_markup = f'<span class="avg-rank">Avg rank {escape(str(avg))}</span>' if avg is not None else ""
            team_sections.append(
                f'<div class="team team-{index % 2}"><div class="team-head">'
                f'<b>Side {escape(team_id)}</b>{avg_markup}</div>'
                f'<ul>{"".join(teams[team_id])}</ul></div>'
            )
        match_section = (
            '<section class="match-section"><div class="match-head"><div>'
            '<span class="live-dot"></span><span class="live-label">LIVE MATCH</span>'
            '<h2>On the battlefield</h2></div><span class="live-pulse">ACTIVE</span></div>'
            + (f'<div class="teams">{"".join(team_sections)}</div>' if team_sections
               else '<p class="empty">Match detected; player roster is not available.</p>')
            + "</section>"
        )
    else:
        match_section = (
            '<section class="match-section idle"><div class="match-head"><div>'
            '<span class="idle-dot"></span><span class="live-label">MATCH STATUS</span>'
            '<h2>Between matches</h2></div></div>'
            '<p class="empty">No active match is linked to this profile right now.</p></section>'
        )

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}}:root{{color-scheme:dark}}body{{margin:0;padding:18px;
background:#0d0f12;color:#f0f1f3;font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:850px;margin:auto}}h1,h2,p{{margin-top:0}}h1{{font-size:26px;line-height:1.12;
letter-spacing:-.025em;margin:3px 0 5px}}h2{{font-size:17px;letter-spacing:-.01em;margin:0}}
.sub,.empty{{color:#a9adb6;font-size:12px;margin:5px 0 0}}.masthead{{display:flex;
justify-content:space-between;align-items:center;padding:3px 1px 16px}}
.identity{{display:flex;align-items:center;gap:13px}}.monogram{{width:42px;height:42px;
display:grid;place-items:center;background:#25282e;border:1px solid #393d45;border-radius:12px;
font-size:14px;font-weight:750;color:#f2f3f5}}.uid{{color:#959aa4;font:11px/1.4 ui-monospace,monospace}}
.state,.section-tag,.live-pulse{{font-size:10px;letter-spacing:.09em;font-weight:750;
border:1px solid #40434b;border-radius:999px;padding:5px 9px;color:#c6c9cf}}
.state.active,.live-pulse{{border-color:#6f3937;color:#ff9b8e;background:#281b1a}}
.overview{{display:grid;grid-template-columns:1.2fr 1fr;gap:12px;margin-bottom:12px}}
.panel,.match-section{{background:#17191e;border:1px solid #2b2e35;border-radius:13px;padding:17px}}
.rank-panel{{background:#202126}}.rank-caption,.section-tag{{color:#aeb2bb}}
.rank-line{{display:flex;align-items:baseline;gap:10px;margin-top:5px}}
.rank-line strong{{font-size:25px;letter-spacing:-.03em}}.rank-line span{{color:#ff9b8e;font-size:12px}}
.competitive-line{{display:flex;gap:13px;flex-wrap:wrap;margin-top:13px;padding-top:12px;
border-top:1px solid #373940;color:#babdc5;font-size:11px;font-variant-numeric:tabular-nums}}
.level-line{{display:flex;gap:20px;align-items:center;height:100%}}.level-value{{font-size:28px;
font-weight:720;letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
.level-copy{{display:grid;gap:1px;color:#a9adb6;font-size:11px}}.level-copy b{{color:#edeef0;
font-size:13px;font-variant-numeric:tabular-nums}}
.match-section{{margin-bottom:12px;padding:0;overflow:hidden}}.match-head{{display:flex;
justify-content:space-between;align-items:center;padding:15px 17px;border-bottom:1px solid #30323a}}
.match-head h2{{margin-top:3px}}.live-label{{color:#ff9b8e;font-size:10px;font-weight:750;
letter-spacing:.1em}}.live-dot,.idle-dot{{display:inline-block;width:7px;height:7px;
border-radius:50%;background:#f47869;margin-right:7px;vertical-align:1px}}
.idle-dot{{background:#797e88}}.teams{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:13px}}
.team{{padding:12px;border-radius:9px;background:#1d2026}}.team-0{{border:1px solid #34515b}}
.team-1{{border:1px solid #60403c}}.team-head{{display:flex;justify-content:space-between;
align-items:center;font-size:12px}}.team-0 .team-head b{{color:#91ceda}}.team-1 .team-head b{{color:#f0a08f}}
.avg-rank{{color:#a9adb6;font-size:10px}}ul{{list-style:none;padding:0;margin:9px 0 0}}
li{{display:grid;gap:2px;padding:8px 0;border-top:1px solid #34363d;min-width:0}}
li span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;font-size:12px}}
li small{{font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.data-grid{{display:grid;grid-template-columns:1.05fr .95fr;gap:12px}}
.section{{background:#17191e;border:1px solid #2b2e35;border-radius:13px;padding:17px;min-width:0}}
.section-head{{display:flex;justify-content:space-between;align-items:start;gap:10px;margin-bottom:12px}}
.section-head h2{{font-size:16px}}.section-tag{{font-size:9px;padding:4px 7px;white-space:nowrap}}
.hero-row{{margin-top:12px}}.hero-label{{display:flex;justify-content:space-between;gap:8px;
margin-bottom:5px;font-size:11px}}.hero-label span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.hero-label b{{font-variant-numeric:tabular-nums}}.track{{height:7px;background:#30333a;
border-radius:2px;overflow:hidden}}.track i{{display:block;height:100%;background:#a8d2a2}}
.hero-row small{{display:block;margin-top:3px;color:#9398a2;font-size:10px}}
.form-strip{{display:flex;gap:5px;margin:16px 0 12px;flex-wrap:wrap}}
.form-mark{{width:25px;height:25px;display:grid;place-items:center;border-radius:5px;
font-size:10px;font-weight:750}}.form-mark.win{{background:#20362d;color:#9bd4ac}}
.form-mark.loss{{background:#3a2627;color:#f1a0a0}}.form-foot{{display:flex;gap:8px 14px;
justify-content:space-between;flex-wrap:wrap;color:#a9adb6;font-size:10px;font-variant-numeric:tabular-nums}}
.empty{{padding:8px 0}}.source-note{{margin:11px 2px 0;color:#777d87;font-size:10px}}
@media(max-width:560px){{body{{padding:12px}}.overview,.data-grid,.teams{{grid-template-columns:1fr}}
.panel,.section{{padding:14px}}.teams{{padding:10px}}.masthead{{align-items:flex-start}}}}
</style></head><body><main>
<header class="masthead"><div class="identity"><span class="monogram">{escape(player_name[:2].upper())}</span>
<div><h1>{name}</h1><div class="uid">PLAYER ID {uid}</div></div></div>
<span class="state {"active" if live else ""}">{"IN MATCH" if live else "PROFILE"}</span></header>
<div class="overview"><section class="panel rank-panel"><div class="rank-caption">COMPETITIVE RANK</div>
<div class="rank-line"><strong>{rank_text}</strong></div>{competitive_summary}</section>
<section class="panel"><div class="level-line"><div class="level-value">{level}</div>
<div class="level-copy"><span>PLAYER LEVEL</span><b>{xp} XP</b><span>Lifetime experience</span></div></div></section></div>
{match_section}
 {f'<div class="data-grid">{hero_chart}{recent_section}</div>' if hero_chart or recent_section else ''}
<p class="source-note">Public Marvel Rivals profile and match data</p>
</main></body></html>"""
    legacy_resource = create_ui_resource({
        "uri": PLAYER_DASHBOARD_URI,
        "content": {"type": "rawHtml", "htmlString": html},
        "encoding": "text",
        "uiMetadata": {"preferred-frame-size": [850, 980]},
        "resourceProps": {"mimeType": "text/html"},
    })
    return CallToolResult(
        content=[
            TextContent(type="text", text=f"Player dashboard for {player_name}."),
            EmbeddedResource(
                type="resource",
                resource=TextResourceContents(
                    uri=PLAYER_DASHBOARD_URI,
                    mimeType="text/html",
                    text=legacy_resource["resource"]["text"],
                ),
            ),
        ],
        structuredContent={"html": html, "section": section},
    )


@mcp.tool()
def get_player_heroes(
    uid_or_name: str, season: int | Literal["current", "all"] | None = None,
    mode: Literal["competitive", "quickplay", "all"] = "all",
    method: Literal["normal", "precise"] = "normal",
) -> Any:
    """Use scoped provider summaries by default, without requesting match history.

    method="precise" verifies completed matches with incremental persistent caching.
    Defaults to the current season and Competitive plus Quickplay; Custom/Arcade
    are excluded. Season accepts "current", a positive provider ID, or "all".
    Sources, counting basis, disagreements and incomplete coverage remain visible.
    """
    return _call(lambda client: client.get_player(uid_or_name).stats.hero_win_rates(
        season=season, mode=mode, method=method))


@mcp.tool()
def get_player_matches(
    uid_or_name: str,
    limit: int | Literal["all"],
    season: int | None = None,
    cursor: str | None = None,
    mode: str | None = None,
    hero: str | None = None,
    teammate: str | None = None,
    cached: bool = True,
) -> Any:
    """Get combined match history with a required positive limit or limit="all".

    Numeric limits return at most that many merged matches and a cursor when
    more remain. "all" follows every available page. Set cached=False to request
    uncached RivalsData history. Mode accepts quickplay/competitive/custom or
    numeric mode IDs 1/2/3.
    """
    def fetch(client: RivalsClient, value: str, **filters: Any) -> Any:
        player = client.get_player(value)
        return player.matches.fetch(**filters)
    return _call(fetch, uid_or_name, limit=limit, season=season, cursor=cursor, mode=mode,
                 hero=hero, teammate=teammate, cached=cached)


@mcp.tool()
def get_player_win_rate(
    uid_or_name: str,
    season: int | Literal["current", "all"] | None = None,
    mode: Literal["competitive", "quickplay", "all"] = "all",
    method: Literal["normal", "precise"] = "normal",
) -> Any:
    """Use scoped provider summaries by default, without requesting match history.

    method="precise" verifies completed matches with incremental persistent caching.
    Defaults to the current season and Competitive plus Quickplay; Custom/Arcade
    are excluded. Season accepts "current", a positive provider ID, or "all".
    Sources, counting basis, disagreements and incomplete coverage remain visible.
    """
    def fetch(client: RivalsClient, value: str, **filters: Any) -> Any:
        return client.get_player(value).stats.win_rate(**filters)
    return _call(fetch, uid_or_name, season=season, mode=mode, method=method)


@mcp.tool()
def get_player_hero_win_rates(
    uid_or_name: str,
    season: int | Literal["current", "all"] | None = None,
    mode: Literal["competitive", "quickplay", "all"] = "all",
    method: Literal["normal", "precise"] = "normal",
) -> Any:
    """Use scoped provider summaries by default, without requesting match history.

    method="precise" verifies completed matches with incremental persistent caching.
    Defaults to the current season and Competitive plus Quickplay; Custom/Arcade
    are excluded. Season accepts "current", a positive provider ID, or "all".
    Sources, counting basis, disagreements and incomplete coverage remain visible.
    """
    return _call(lambda client, value, **filters:
                 client.get_player(value).stats.hero_win_rates(**filters),
                 uid_or_name, season=season, mode=mode, method=method)


@mcp.tool()
def get_player_class_win_rates(
    uid_or_name: str,
    season: int | Literal["current", "all"] | None = None,
    mode: Literal["competitive", "quickplay", "all"] = "all",
    method: Literal["normal", "precise"] = "normal",
) -> Any:
    """Use scoped provider summaries by default, without requesting match history.

    method="precise" verifies completed matches with incremental persistent caching.
    Defaults to the current season and Competitive plus Quickplay; Custom/Arcade
    are excluded. Season accepts "current", a positive provider ID, or "all".
    Sources, counting basis, disagreements and incomplete coverage remain visible.
    """
    return _call(lambda client, value, **filters:
                 client.get_player(value).stats.class_win_rates(**filters),
                 uid_or_name, season=season, mode=mode, method=method)


@mcp.tool()
def get_player_stats(
    uid_or_name: str, category: str = "heroes",
    season: int | Literal["current", "all"] | None = None,
    mode: Literal["competitive", "quickplay", "all"] = "all",
    method: Literal["normal", "precise"] = "normal",
) -> Any:
    """Use scoped provider summaries by default, without requesting match history.

    method="precise" verifies completed matches with incremental persistent caching.
    Defaults to the current season and Competitive plus Quickplay; Custom/Arcade
    are excluded. Season accepts "current", a positive provider ID, or "all".
    Sources, counting basis, disagreements and incomplete coverage remain visible.
    """
    methods = {"heroes": "heroes", "maps": "maps", "bans": "bans", "classes": "classes"}
    if category not in methods:
        raise ValueError("category must be one of: heroes, maps, bans, classes")
    def fetch(client: RivalsClient, value: str, category: str,
              season: int | Literal["current", "all"] | None,
              mode: Literal["competitive", "quickplay", "all"]) -> Any:
        from .stat_scope import resolve_season

        player = client.get_player(value)
        if category not in ("heroes", "classes") and season == "current":
            season = resolve_season(player.stats, season)
        season_id = season if category in ("heroes", "classes") else -1 if season == "all" else season
        filters: dict[str, Any] = {"season": season_id}
        if category in ("heroes", "classes"):
            filters["mode"] = mode
            filters["method"] = method
        if category == "heroes":
            return player.stats.hero_win_rates(**filters)
        return getattr(player.stats, methods[category])(**filters)
    return _call(fetch, uid_or_name, category, season, mode)


@mcp.tool()
def get_player_teammates(
    uid_or_name: str, season: int | None = None, mode: str | None = None
) -> Any:
    """Get a player's public teammate statistics."""
    def fetch(client: RivalsClient, value: str, **filters: Any) -> Any:
        return client.get_player(value).teammates.fetch(**filters)
    return _call(fetch, uid_or_name, season=season, mode=mode)


@mcp.tool()
def get_leaderboard(
    limit: int = 100, skip: int = 0, season: int | None = None,
    platform: int | None = None,
) -> Any:
    """Get the global ranked-player leaderboard (platform 1 is PC)."""
    return _call(lambda client, **kw: client.leaderboards.fetch(**kw),
                 limit=limit, skip=skip, season=season, platform=platform)


@mcp.tool()
def get_hero_tier_list(platform: int = 1, rank: str = "grandmaster_plus") -> Any:
    """Get hero tier-list statistics for a platform and rank range."""
    return _call(lambda client, **kw: client.heroes.tier_list(**kw),
                 platform=platform, rank=rank)


@mcp.tool()
def get_hero_stats(hero_id: str) -> Any:
    """Get aggregate statistics for a hero ID."""
    return _call(lambda client, value: client.heroes.get(value), hero_id)


@mcp.tool()
def resolve_hero(hero: str) -> dict[str, Any]:
    """Resolve a Marvel Rivals hero name or ID to both canonical name and ID."""
    identifier = int(hero) if hero.isdecimal() else hero_id(hero)
    if identifier is None:
        raise ValueError(f"Unknown hero name or ID: {hero}")
    return {"hero_id": identifier, "hero_name": hero_name(identifier)}


@mcp.tool()
def get_hero_meta(hero_id: str, days: int = 90) -> Any:
    """Get hero trends for 30, 90, or 180 days."""
    if days not in (30, 90, 180):
        raise ValueError("days must be 30, 90, or 180")
    return _call(lambda client, value, period: client.heroes.meta(value, range=period),
                 hero_id, days)


@mcp.tool()
def get_team_ups(platform: int = 1, rank: str = "grandmaster_plus") -> Any:
    """Get team-up usage and win-rate statistics."""
    return _call(lambda client, **kw: client.team_ups.fetch(**kw),
                 platform=platform, rank=rank)


@mcp.tool()
def get_public_insight(kind: str = "xp", cursor: str | None = None,
                       mode: str = "all", platform: int = 1) -> Any:
    """Get public XP, Top 500, comm-ban, leaver, or punishment insights."""
    def fetch(client: RivalsClient, kind: str, cursor: str | None,
              mode: str, platform: int) -> Any:
        if kind == "xp":
            return client.insights.xp(cursor=cursor)
        if kind == "top_500":
            return client.insights.top_500(platform=platform)
        if kind == "commbans":
            return client.insights.commbans(mode=mode)
        if kind == "leavers":
            return client.insights.leavers(mode=mode)
        if kind == "punishments":
            return client.insights.punishments(kind=mode, cursor=cursor)
        raise ValueError("kind must be xp, top_500, commbans, leavers, or punishments")
    return _call(fetch, kind, cursor, mode, platform)


@mcp.tool()
def get_match(match_id: str, refresh: bool = False) -> Any:
    """Get combined typed match details and stats, with source conflicts/errors.

    Set refresh to bypass detail/provider read caches. This does not submit an
    upstream refresh request or guarantee complete in-game data.
    """
    return _call(lambda client, value: client.matches.get(value, refresh=refresh), match_id)


@mcp.tool()
def get_faction(faction_id: str) -> Any:
    """Get public faction details and member information."""
    return _call(lambda client, value: client.factions.get(value), faction_id)



@mcp.tool()
def search_player_candidates(name: str) -> list[dict[str, Any]]:
    """Compatibility alias for search_players: return names and game UIDs."""
    return search_players(name)


@mcp.tool()
def get_player_rank_history(uid_or_name: str, season: int | None = None) -> Any:
    """Rank timeline, match-linked score changes, promotions and season summary."""
    return _call(lambda c: c.get_player(uid_or_name).analytics.rank_history(season=season))


@mcp.tool()
def get_player_cosmetics(uid_or_name: str) -> Any:
    """Observed skin usage, performance and dates; not owned inventory."""
    return _call(lambda c: c.get_player(uid_or_name).analytics.cosmetics())


@mcp.tool()
def get_player_encounters(uid_or_name: str, season: int | None = None,
                          mode: str = "all", local_offset: int = 0) -> Any:
    """Teammates and opponents with encounter counts, recency and season stats."""
    return _call(lambda c: c.get_player(uid_or_name).analytics.encounters(
        season=season, mode=mode, local_offset=local_offset))


@mcp.tool()
def get_player_career(uid_or_name: str, season: int | Literal["all"] | None = None,
                      mode: str = "all") -> Any:
    """Detailed combat, percentile/display metadata and hero/role career segments.

    Hero participation counts can be fractional. All seasons returns separate
    season segments; these cannot establish unique match counts.
    """
    return _call(lambda c: c.get_player(uid_or_name).stats.career(season=season, mode=mode))


@mcp.tool()
def get_player_matchups(uid_or_name: str, season: int | None = None) -> Any:
    """Player results against each enemy hero."""
    return _call(lambda c: c.get_player(uid_or_name).stats.matchups(season=season))


@mcp.tool()
def get_player_seasons(uid_or_name: str) -> Any:
    """Named full/half-season catalog and provider current/default season IDs."""
    return _call(lambda c: c.get_player(uid_or_name).analytics.seasons())


@mcp.tool()
def get_player_rank_stats(uid_or_name: str, season: int | None = None) -> Any:
    """Tracker rank-stat timeline and any available ranking metadata."""
    return _call(lambda c: c.get_player(uid_or_name).analytics.rank_stats(season=season))


@mcp.tool()
def get_player_crosshairs(uid_or_name: str) -> Any:
    """Get the player's existing RivalsData crosshair codes and usage."""
    return _call(lambda c: c.get_player(uid_or_name).crosshairs.fetch())


@mcp.tool()
def get_player_proficiency(uid_or_name: str) -> Any:
    """Get public hero proficiency points and levels."""
    return _call(lambda c: c.get_player(uid_or_name).proficiency.fetch())


@mcp.tool()
def get_player_punishments(uid_or_name: str, historical: bool = False) -> Any:
    """Current sanctions, or RivalsTracker's historical punishment records."""
    return _call(lambda c: c.get_player(uid_or_name).punishments.history() if historical
                 else c.get_player(uid_or_name).punishments.fetch())


@mcp.tool()
def get_player_name_history(uid_or_name: str, events: bool = False) -> Any:
    """Names and first/last detection, or match-linked name-change events."""
    return _call(lambda c: c.get_player(uid_or_name).name_history.events() if events
                 else c.get_player(uid_or_name).name_history.fetch())


@mcp.tool()
def get_hero_leaderboard(hero_id: str) -> Any:
    """Get the existing hero-specific RivalsData leaderboard."""
    return _call(lambda c: c.heroes.leaderboard(hero_id))


@mcp.tool()
def get_public_profile(uid_or_name: str) -> Any:
    """Get existing public profile-card metadata."""
    return _call(lambda c: c.profiles.get(uid_or_name))


@mcp.tool()
def get_favorite_players(uids: list[str]) -> Any:
    """Read profile summaries for supplied favorite UIDs; no account mutation."""
    return _call(lambda c: c.favorites.fetch(uids))


@mcp.tool()
def get_hero_reference(hero_id: str | None = None) -> Any:
    """Dated hero catalog with abilities, passives, form stats and team-up descriptions."""
    return _call(lambda c: c.heroes.reference(hero_id))


@mcp.tool()
def get_hero_matchups(hero_id: str | None = None) -> Any:
    """Global enemy-hero matchup matrix; fixed provider scope, not causal counters."""
    return _call(lambda c: c.heroes.matchups(hero_id))


@mcp.tool()
def get_hero_combat_history(hero_id: str, days: int = 30, platform: str = "pc") -> Any:
    """Daily hero combat/meta trends scoped to Celestial+ and PC/console."""
    return _call(lambda c: c.heroes.history(hero_id, days=days, platform=platform))


@mcp.tool()
def get_season_meta(season: int | None = None) -> Any:
    """Hero meta by rank, mirror counts, ban denominators, hero-map stats and team-ups."""
    return _call(lambda c: c.heroes.season_stats(season=season))


@mcp.tool()
def get_team_compositions() -> Any:
    """Rank-bucketed team-role composition match/win statistics."""
    return _call(lambda c: c.team_ups.compositions())


@mcp.tool()
def get_rank_distribution() -> Any:
    """Tracked-player rank counts and percentages; not the whole game population."""
    return _call(lambda c: c.analytics.rank_distribution())


@mcp.tool()
def get_skin_popularity() -> Any:
    """Global skin usage counts; not player-owned cosmetics."""
    return _call(lambda c: c.analytics.skin_popularity())


@mcp.tool()
def get_hero_players(hero_id: str, season: int | None = None, device: int = 1) -> Any:
    """Alternative hero leaderboard with cumulative combat/playtime statistics."""
    return _call(lambda c: c.analytics.hero_players(hero_id, season=season, device=device))


@mcp.tool()
def get_community_crosshairs(page: int = 1, sort: str = "upvotes", players: str = "all",
                             search: str | None = None, name: str | None = None) -> Any:
    """Read community crosshair codes, rankings and author metadata."""
    return _call(lambda c: c.community.crosshairs(
        page=page, sort=sort, players=players, search=search, name=name))


@mcp.tool()
def get_looking_for_group(region: str = "all", platform: str = "all",
                           playlist: str = "all", roles: list[str] | None = None) -> Any:
    """Read public LFG listings; no posting or contact action."""
    return _call(lambda c: c.community.looking_for_group(
        region=region, platform=platform, playlist=playlist, roles=roles or []))


# Uvicorn/ASGI entry point for remote Streamable HTTP deployments.
app = mcp.streamable_http_app()


def main() -> None:
    """Start the server over stdio for local desktop clients."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
