import time

import pytest

from rivalsdata import Player, RivalsDataClient
from rivalsdata.normalize import merge, tracker_stats
from rivalsdata.selection import update_time


def record(value, source="rivalsdata", **evidence):
    return {"assists": value, "provider_metadata": {
        "sources": [source], "evidence": {source: evidence}}}


def test_three_comparable_sources_resolve_a_two_source_tie():
    first = merge(record(12), record(1, "rivalstracker"), "rivalstracker")
    assert first["assists"] == 12
    assert first["provider_metadata"]["selections"]["assists"]["confidence"] == "uncertain"
    final = merge(first, record(1, "tracker"), "tracker")
    assert final["assists"] == 1
    selection = final["provider_metadata"]["selections"]["assists"]
    assert selection["reason"] == "cross_provider_agreement"
    assert final["provider_metadata"]["conflicts"][0]["alternative"] == 12
    assert final["provider_metadata"]["conflicts"][0]["selected"] == 1


def test_repeated_same_source_does_not_create_fake_consensus():
    result = merge(record(12), record(1, "tracker"), "tracker")
    result = merge(result, record(1, "tracker"), "tracker")
    assert result["assists"] == 12
    assert len(result["provider_metadata"]["observations"]["assists"]) == 2


def test_completed_detail_beats_summary_even_when_two_summaries_agree():
    result = merge(record(12, kind="match_summary"),
                   record(12, "rivalstracker", kind="match_summary"), "rivalstracker")
    result = merge(result, record(1, "tracker", kind="match_detail", complete=True), "tracker")
    assert result["assists"] == 1
    assert result["provider_metadata"]["selections"]["assists"]["reason"] == "more_complete_record"


@pytest.mark.parametrize("complete", [False, None])
def test_incomplete_detail_does_not_outrank_agreeing_summaries(complete):
    result = merge(record(12, kind="match_summary"),
                   record(12, "rivalstracker", kind="match_summary"), "rivalstracker")
    result = merge(result, record(1, "tracker", kind="match_detail", complete=complete), "tracker")
    assert result["assists"] == 12
    assert result["provider_metadata"]["selections"]["assists"]["reason"] == "cross_provider_agreement"


def test_newer_real_update_beats_stale_agreement():
    now = time.time()
    result = merge(record(12, updated_at=now - 600),
                   record(12, "rivalstracker", updated_at=now - 600), "rivalstracker")
    result = merge(result, record(1, "tracker", updated_at=now - 20), "tracker")
    assert result["assists"] == 1
    assert result["provider_metadata"]["selections"]["assists"]["reason"] == "newer_verified_update"


@pytest.mark.parametrize("bad", ["2000-01-01T00:00:00+00:00", "0001-01-01", float("nan"), time.time() + 3600])
def test_invalid_and_sentinel_timestamps_are_not_freshness_evidence(bad):
    assert update_time(bad) is None
    result = merge(record(12, updated_at=time.time() - 100),
                   record(1, "tracker", updated_at=bad), "tracker")
    assert result["assists"] == 12


def test_millisecond_update_times_are_normalized():
    now = time.time()
    assert update_time(now * 1000) == pytest.approx(now)


def test_scopes_and_units_cannot_vote_each_other_out():
    original = record(12, scope={"season": 20, "mode": "competitive"}, unit="count")
    all_modes = record(1, "rivalstracker", scope={"season": 20, "mode": "all"}, unit="count")
    old_season = record(1, "tracker", scope={"season": 19, "mode": "competitive"}, unit="count")
    result = merge(merge(original, all_modes, "rivalstracker"), old_season, "tracker")
    assert result["assists"] == 12
    result = merge(record(12, unit="seconds"), record(12000, "tracker", unit="milliseconds",
                                                   updated_at=time.time()), "tracker")
    assert result["assists"] == 12


def test_count_group_selection_and_derived_rates_are_coherent():
    scope = {"season": 20, "mode": "competitive", "counts_basis": "hero_participation"}
    primary = {"games": 79, "wins": 44, "losses": 35, "winrate": 55.7, "kda": 8,
               "kills": 395, "deaths": 60, "assists": 85,
               "per_game": {"kills": 5, "finals": 2}, "per_10": {"kills": 6},
               "provider_metadata": {"sources": ["rivalsdata"]}}
    rt = {"games": 77, "wins": 44, "losses": 33,
          "kills": 154, "deaths": 22, "assists": 66, "play_time": 4620}
    result = merge(primary, rt, "rivalstracker", primary_context={"scope": scope}, context={"scope": scope})
    result = merge(result, {"games": 77, "wins": 44, "losses": 33}, "tracker", context={"scope": scope})
    assert (result["games"], result["wins"], result["losses"]) == (77, 44, 33)
    assert result["winrate"] == pytest.approx(44 * 100 / 77)
    assert result["per_game"]["kills"] == 2
    assert result["kills"] == 154
    assert result["deaths"] == 22
    assert result["assists"] == 66
    assert result["per_game"]["finals"] is None  # Old population's value isn't reused.
    assert result["per_10"]["kills"] == 20
    assert result["kda"] == 10
    # A later update with unchanged counts must refresh totals and averages too.
    result = merge(result, {**rt, "kills": 231}, "rivalstracker", context={"scope": scope})
    assert result["kills"] == 231
    assert result["per_game"]["kills"] == 3
    assert result["provider_metadata"]["derived_values"]["kills"]["value"] == 231


def test_invalid_counts_are_replaced_as_one_group():
    result = merge({"games": 10, "wins": 12, "losses": -2},
                   {"games": 10, "wins": 7, "losses": 3}, "tracker")
    assert (result["games"], result["wins"], result["losses"]) == (10, 7, 3)


def test_unusable_counts_cannot_keep_old_rates_or_totals():
    result = merge({"games": 10, "wins": 12, "losses": -2,
                    "winrate": 120, "kills": 50, "per_game": {"kills": 5}},
                   {"games": 10, "wins": 13, "losses": -3}, "tracker")
    assert result["games"] is None
    assert result["winrate"] is None
    assert result["kills"] is None
    assert result["per_game"]["kills"] is None


def test_rank_update_order_does_not_change_freshness_choice():
    old, new = time.time() - 300, time.time() - 10
    result = merge({"update_time": old, "rank_score": 4000},
                   {"update_time": new, "rank_score": 4200}, "rivalstracker")
    assert result["rank_score"] == 4200


def test_tracker_time_seconds_and_milliseconds_have_equal_normalized_units():
    def segment(value, kind):
        return {"stats": {"timePlayed": {"value": value, "displayType": kind}}}

    seconds = tracker_stats(segment(4648, "TimeSeconds"))
    millis = tracker_stats(segment(4648000, "TimeMilliseconds"))
    assert seconds["play_time"] == millis["play_time"] == 4648
    assert "play_time_ms" not in seconds
    assert millis["play_time_ms"] == 4648000
    assert "play_time" not in tracker_stats(segment(4648, "Unknown"))


def test_profile_career_summary_does_not_relabel_rank_system_counts(monkeypatch):
    with RivalsDataClient() as client:
        monkeypatch.setattr(client, "_post_json", lambda *a: {
            "uid": 123, "name": "Example", "rank_game_season": {
                "1001020": {"rank_game_id": 20, "battle_count": 79, "win_count": 44}}})
        body = {"player": {"_id": 123, "info": {"name": "Example"}},
                "stats": {"ranked_matches": 77, "ranked_matches_wins": 44}}
        monkeypatch.setattr(client.providers.rt, "request", lambda *a, **k: body)
        monkeypatch.setattr(client.providers.tracker, "request", lambda *a, **k: [{
            "type": "overview", "attributes": {"season": 20, "mode": "competitive"},
            "stats": {"matchesPlayed": {"value": 77}, "matchesWon": {"value": 44}}}])
        player = client.get_player(123)
        assert player.rank_game_season["1001020"].battle_count == 79
        assert player.career_summary.competitive.games == 77
        assert player.win_rate == 57
        assert player.career_summary.competitive.provider_metadata.selections["@counts"].reason == "cross_provider_agreement"
    legacy = Player({"uid": 123, "rank_game_season": {
        "1001020": {"rank_game_id": 20, "battle_count": 79, "win_count": 44}}}, None)
    assert legacy.win_rate == 56
