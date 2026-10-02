import asyncio

import pytest

from rivals_api import RivalsClient

server = pytest.importorskip("rivals_api.mcp_server", exc_type=ImportError)


@pytest.fixture
def client(monkeypatch):
    with RivalsClient(enrich=False) as client:
        def unexpected(*args, **kwargs):
            raise AssertionError("Unexpected network request or name resolution")

        monkeypatch.setattr(client, "_post_json", unexpected)
        monkeypatch.setattr(client, "resolve_player", unexpected)
        monkeypatch.setattr(client.providers.rt, "request", unexpected)
        monkeypatch.setattr(client.providers.tracker, "request", unexpected)
        monkeypatch.setattr(
            server, "_call",
            lambda fn, *args, **kwargs: server._plain(fn(client, *args, **kwargs)),
        )
        yield client


@pytest.mark.parametrize("tool", [server.search_players, server.search_player_candidates])
def test_search_returns_multiple_candidates_preserving_unicode(client, monkeypatch, tool):
    requests = []

    def search(path, *, payload):
        requests.append((path, payload))
        return [
            {"aid": "1254981449", "name": "Silo"},
            {"aid": "283622404", "name": "siloء", "cur_head_icon_id": "31048204"},
        ]

    monkeypatch.setattr(client.providers.rt, "request", search)
    result = tool("silo")

    assert requests == [("/find-player", {"name": "silo"})]
    assert [(row["name"], row["uid"]) for row in result] == [
        ("Silo", 1254981449), ("siloء", 283622404),
    ]
    assert result[1]["cur_head_icon_id"] == "31048204"


def test_search_without_matches_returns_empty_list(client, monkeypatch):
    monkeypatch.setattr(client.providers.rt, "request", lambda *args, **kwargs: [])
    assert server.search_players("missing") == []


def test_profile_fetches_selected_uid_without_name_search(client, monkeypatch):
    requests = []

    def profile(path, payload):
        requests.append((path, payload))
        return {
            "uid": 283622404, "name": "siloء", "level": 100,
            "rank_game_season": {"1001020": {"battle_count": 10, "win_count": 6}},
        }

    monkeypatch.setattr(client, "_post_json", profile)
    result = server.get_player_profile(283622404)

    assert requests == [("/player", {"uid": 283622404})]
    assert (result["uid"], result["name"], result["level"]) == (283622404, "siloء", 100)
    assert result["win_rate"] == 60


@pytest.mark.parametrize("uid", [0, -1, True, "silo", None, 283622404.5])
def test_profile_rejects_invalid_uid_before_fetching(client, uid):
    with pytest.raises(ValueError, match="positive integer"):
        server.get_player_profile(uid)


def test_mcp_registers_list_search_and_uid_profile_schemas():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    profile_schema = tools["get_player_profile"].inputSchema
    assert profile_schema["required"] == ["uid"]
    assert profile_schema["properties"]["uid"]["type"] == "integer"
    search_schema = tools["search_players"].outputSchema
    assert search_schema["properties"]["result"]["type"] == "array"
