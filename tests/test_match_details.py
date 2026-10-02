"""Public history-to-detail flow and adversarial multi-provider reconciliation."""

import json
from copy import deepcopy

import pytest

from rivals_api import Match, MatchPlayer, MatchTeam, RivalsClient, RivalsDataHTTPError
from rivals_api.models import Character
from rivals_api.normalize import merge_match, rd_match, rt_match, tracker_match
from rivals_api.resources import PlayerMatches


@pytest.fixture
def client(monkeypatch):
    with RivalsClient() as c:
        c._match_detail_cache.clear()

        def unexpected(*args, **kwargs):
            raise AssertionError("Unexpected network request")

        monkeypatch.setattr(c, "_post_json", unexpected)
        monkeypatch.setattr(c.providers.rt, "request", unexpected)
        monkeypatch.setattr(c.providers.tracker, "request", unexpected)
        yield c
        c._match_detail_cache.clear()


def rd_body(mid="detail-flow"):
    return {"match_uid": mid, "teams": [{"camp": 0, "players": [
        {"player_uid": "1", "name": "Alpha", "camp": 0, "kills": 27, "assists": 12,
         "accuracy": 46.3, "blocked": 99, "heroes": [
             {"hero_id": 1011, "accuracy": .25, "play_time": 30}]}]}]}


def rt_body(mid="detail-flow"):
    return {"match_uid": mid, "match_players": [
        {"player_uid": 1, "nick_name": "Alpha", "camp": 0, "k": 28, "a": 1,
         "session_hit_rate": .6, "total_damage_taken": 150, "player_heroes": [
             {"hero_id": 1011, "k": 28, "a": 1, "play_time": 30}]},
        {"player_uid": 2, "nick_name": "Beta", "camp": 1, "k": 10}]}


def tracker_body(mid="detail-flow", *, complete=True):
    def segment(name, account, camp, kills):
        return {"type": "player", "attributes": {"accountId": account},
                "metadata": {"platformInfo": {"platformUserIdentifier": name}, "teamId": camp},
                "stats": {"kills": {"value": kills}, "assists": {"value": 1},
                          "sessionHitRate": {"value": .6}, "headKills": {"value": 5}}}

    return {"attributes": {"id": mid},
            "metadata": {"fullMatchAvailable": True, "fullMatchFetched": complete},
            "segments": [segment("Alpha", "trn-alpha", 0, 28),
                         segment("Gamma", "trn-gamma", 1, 3),
                         {"type": "hero", "attributes": {"accountId": "trn-alpha", "heroId": 1011},
                          "stats": {"kills": {"value": 28}, "sessionHitRate": {"value": .7},
                                    "mainAttacks": {"value": 100}, "mainAttackHits": {"value": 40}}}]}


def mock_details(client, monkeypatch):
    calls = []

    def rd(path, payload):
        calls.append(("rivalsdata", path, payload))
        return rd_body(payload["match_id"])

    def provider(source, factory):
        def request(path, **kwargs):
            calls.append((source, path, kwargs))
            return factory(path.rsplit("/", 1)[-1])
        return request

    monkeypatch.setattr(client, "_post_json", rd)
    monkeypatch.setattr(client.providers.rt, "request", provider("rivalstracker", rt_body))
    monkeypatch.setattr(client.providers.tracker, "request", provider("tracker", tracker_body))
    return calls


@pytest.mark.parametrize("fetch_style", ["bounded", "all", "iter"])
def test_history_rows_from_both_sources_fetch_lazy_typed_details(client, monkeypatch, fetch_style):
    calls = mock_details(client, monkeypatch)
    detail_rd, detail_rt = client._post_json, client.providers.rt.request

    def post(path, payload):
        if path == "/match":
            return detail_rd(path, payload)
        return {"matches": [{"match_uid": "rd-only"}], "next_cursor": None}

    def rt(path, **kwargs):
        if path.startswith("/matches/"):
            return detail_rt(path, **kwargs)
        return [{"match_uid": "rt-only", "match_player": {"k": 9}}]

    monkeypatch.setattr(client, "_post_json", post)
    monkeypatch.setattr(client.providers.rt, "request", rt)
    history = PlayerMatches(client, 1)
    rows = (list(history.iter()) if fetch_style == "iter" else
            history.fetch(limit="all" if fetch_style == "all" else 20).matches)
    assert {m.match_uid for m in rows} == {"rd-only", "rt-only"}
    assert calls == []  # History doesn't eagerly download any detail.
    for match in rows:
        before = match.to_dict()
        details = match.get_details()
        assert isinstance(details, Match)
        assert details.match_uid == match.match_uid
        assert isinstance(details.teams[0], MatchTeam)
        assert isinstance(details.teams[0].players[0], MatchPlayer)
        assert isinstance(details.teams[0].players[0].heroes[0], Character)
        assert len([p for t in details.teams for p in t.players]) == 3
        assert match.to_dict() == before
        assert "_client" not in details.to_dict()
    assert len(calls) == 6


def test_details_preserve_accuracy_units_raw_stats_and_field_choices(client, monkeypatch):
    mock_details(client, monkeypatch)
    result = client.matches.get("detail-flow")
    alpha = result.teams[0].players[0]
    assert alpha.accuracy == alpha.accuracy_percent == 46.3
    assert alpha.session_hit_rate == .6
    assert alpha.blocked == 99 and alpha.damage_taken == 150
    assert alpha.heroes[0].accuracy == .25
    assert alpha.heroes[0].accuracy_percent == 25
    assert alpha.heroes[0].session_hit_rate == .7
    assert alpha.heroes[0].mainAttacks == 100
    assert alpha.heroes[0].kills == 28 and alpha.head_kills == 5
    assert alpha.kills == 28 and alpha.assists == 1
    assert alpha.provider_metadata.selections.assists.reason == "cross_provider_agreement"
    assert alpha.provider_metadata.selections.accuracy.source == "rivalsdata"
    assert any(c.field == "kills" and c.alternative == 27 for c in alpha.provider_metadata.conflicts)
    beta = next(p for t in result.teams for p in t.players if p.name == "Beta")
    assert beta.provider_metadata.selections.kills.source == "rivalstracker"
    assert result.provider_metadata.responses.rivalstracker.match_players[0].session_hit_rate == .6
    assert result.provider_metadata.completeness.all_requested_providers_succeeded is True


@pytest.mark.parametrize("bad_accuracy", [None, "NaN", float("nan"), float("inf"), -1, 101, True])
def test_invalid_accuracy_is_missing_and_never_replaced_with_session_hit_rate(client, monkeypatch, bad_accuracy):
    mock_details(client, monkeypatch)
    body = rd_body()
    body["teams"][0]["players"][0]["accuracy"] = bad_accuracy
    monkeypatch.setattr(client, "_post_json", lambda *a: deepcopy(body))
    result = client.matches.get("detail-flow")
    assert result.teams[0].players[0].accuracy is None
    assert result.teams[0].players[0].accuracy_percent is None
    assert result.teams[0].players[0].session_hit_rate == .6
    json.dumps(result.to_dict(), allow_nan=False)


def test_complete_cache_isolated_from_mutations_and_refresh_requeries_providers(client, monkeypatch):
    calls = mock_details(client, monkeypatch)
    result = client.matches.get("detail-flow")
    result.raw["teams"][0]["players"][0]["kills"] = 999
    again = result.get_details()
    assert again.teams[0].players[0].kills == 28
    assert len(calls) == 3
    result.get_details(refresh=True)
    assert len(calls) == 6
    assert calls[-1][2] == calls[-2][2] == {"refresh": True}


def test_enrichment_setting_cannot_reuse_other_modes_cache(client, monkeypatch):
    calls = mock_details(client, monkeypatch)
    client.enrich = False
    first = client.matches.get("detail-flow")
    assert first.provider_metadata.sources == ["rivalsdata"]
    assert len(calls) == 1
    client.enrich = True
    combined = client.matches.get("detail-flow")
    assert combined.provider_metadata.sources == ["rivalsdata", "rivalstracker", "tracker"]
    assert len(calls) == 4
    client.enrich = False
    assert client.matches.get("detail-flow").teams[0].players[0].kills == 27
    assert len(calls) == 4


def test_partial_outage_keeps_successful_details_and_retries(client, monkeypatch):
    calls = mock_details(client, monkeypatch)
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: (_ for _ in ()).throw(RivalsDataHTTPError("offline")))
    partial = client.matches.get("detail-flow")
    assert partial.teams[0].players[0].accuracy_percent == 46.3
    assert partial.provider_metadata.errors[0].source == "tracker"
    assert partial.provider_metadata.completeness.all_requested_providers_succeeded is False
    assert ("detail-flow", True) in client._match_detail_cache
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: tracker_body())
    complete = partial.get_details()
    assert complete.provider_metadata.errors == []
    assert complete.provider_metadata.completeness.all_requested_providers_succeeded is True
    assert len(calls) == 4  # RD and RT were both requested again.


@pytest.mark.parametrize("bad_rd", [{"match_uid": "wrong", "teams": []},
                                    {"match_uid": "detail-flow", "teams": [{"players": "broken"}]}])
def test_bad_primary_match_cannot_contaminate_fallback(client, monkeypatch, bad_rd):
    mock_details(client, monkeypatch)
    monkeypatch.setattr(client, "_post_json", lambda *a: deepcopy(bad_rd))
    result = client.matches.get("detail-flow")
    assert result.match_uid == "detail-flow"
    assert result.provider_metadata.sources == ["rivalstracker", "tracker"]
    assert result.provider_metadata.errors[0].source == "rivalsdata"
    assert result.teams[0].players[0].kills == 28
    assert result.teams[0].players[0].get("accuracy_percent") is None


def test_unresolved_two_provider_disagreement_is_visible(client, monkeypatch):
    mock_details(client, monkeypatch)
    monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: (_ for _ in ()).throw(RivalsDataHTTPError("offline")))
    player = client.matches.get("detail-flow").teams[0].players[0]
    assert player.kills == 27
    assert player.provider_metadata.selections.kills.confidence == "uncertain"
    assert any(c.field == "kills" and c.alternative == 28 for c in player.provider_metadata.conflicts)


def test_tracker_incomplete_flags_cannot_overrule_completed_details():
    first = merge_match(rd_match(rd_body()), rt_match(rt_body()), "rivalstracker")
    incomplete = merge_match(first, tracker_match(tracker_body(complete=False)), "tracker")
    assert incomplete["teams"][0]["players"][0]["kills"] == 27


def test_ambiguous_tracker_names_remain_unjoined_instead_of_duplicating_roster():
    primary = rd_body()
    primary["teams"][0]["players"].append({"player_uid": "9", "name": "Alpha", "camp": 0, "kills": 7})
    result = merge_match(rd_match(primary), tracker_match(tracker_body()), "tracker")
    alpha = result["teams"][0]["players"]
    assert len(alpha) == 2 and [p["kills"] for p in alpha] == [27, 7]
    assert result["provider_metadata"]["unmatched_players"][0]["reason"] == "ambiguous_player_identity"


def test_uid_wins_over_name_and_cross_team_name_is_not_a_bridge():
    primary = rd_match(rd_body())
    incoming = rt_body()
    incoming["match_players"][0]["nick_name"] = "Renamed"
    result = merge_match(primary, rt_match(incoming), "rivalstracker")
    assert len(result["teams"][0]["players"]) == 1
    tracker = tracker_body()
    tracker["segments"][0]["metadata"]["teamId"] = 1
    result = merge_match(primary, tracker_match(tracker), "tracker")
    assert result["teams"][0]["players"][0]["kills"] == 27
    assert result["provider_metadata"]["unmatched_players"]


def test_all_provider_failures_raise_clear_error_and_detached_matches_fail_helpfully(client, monkeypatch):
    def fail(*a, **k):
        raise RivalsDataHTTPError("offline")
    monkeypatch.setattr(client, "_post_json", fail)
    monkeypatch.setattr(client.providers.rt, "request", fail)
    monkeypatch.setattr(client.providers.tracker, "request", fail)
    with pytest.raises(RivalsDataHTTPError, match="No provider returned"):
        client.matches.get("detail-flow")
    with pytest.raises(RuntimeError, match="not attached"):
        Match({"match_uid": "detail-flow"}).get_details()
    with pytest.raises(ValueError, match="no match_uid"):
        Match({}, client=client).get_details()
