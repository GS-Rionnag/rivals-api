from copy import deepcopy

import pytest

from rivals_api import PrivacyError, RivalsClient, RivalsDataHTTPError
from rivals_api.ranks import tracker_ranks
from rivals_api.resources import PlayerStats


def offline(*args, **kwargs):
    raise RivalsDataHTTPError('HTTP 429')


def test_search_falls_back_to_rivalsdata(monkeypatch):
    with RivalsClient() as client:
        monkeypatch.setattr(client.providers.rt, 'request', offline)
        monkeypatch.setattr(client, '_post_json', lambda *a, **k: {'players': [{'name': 'test', 'uid': 123}]})
        assert client.search_players('test')[0].uid == 123


def profile(name='A G N 1', *, private=True):
    def rank(score, tier, **meta):
        return {'value': score, 'metadata': {'tierName': tier, **meta}}
    return {'platformInfo': {'platformUserIdentifier': name},
            'metadata': {'currentSeason': 20, 'isPrivateCareerOverview': private,
                         'isPrivateCareerStatistics': private},
            'segments': [
                {'type': 'overview', 'attributes': {'season': 20, 'mode': 'all'},
                 'stats': {'ranked': rank(4609, 'Grandmaster II')}},
                {'type': 'ranked-peaks', 'attributes': {},
                 'stats': {'lifetimePeakRanked': rank(4894, 'Celestial III', season=19)}}]}


def test_private_tracker_ranks_are_retained_and_marked():
    result = tracker_ranks(profile(), 'A G N 1')
    assert result['current']['rank_score'] == 4609
    assert result['peak']['rank_score'] == 4894
    assert result['peak_scope'] == 'lifetime'
    assert result['private_profile'] is True
    assert tracker_ranks(profile('different account'), 'A G N 1') is None


def test_profile_rank_fallback_when_primary_is_limited(monkeypatch):
    with RivalsClient() as client:
        monkeypatch.setattr(client, '_post_json', offline)
        monkeypatch.setattr(client.providers.rt, 'request', lambda *a, **k: {
            'player': {'_id': 356331488, 'info': {'name': 'A G N 1'}}})
        monkeypatch.setattr(client.providers.tracker, 'request', lambda *a, **k: profile())
        player = client.get_player(356331488)
        assert player.rank_summary.current.tier_name == 'Grandmaster II'
        assert player.rank_summary.peak.tier_name == 'Celestial III'
        rows = list(player.rank_game_season.values())
        assert next(r for r in rows if r.rank_game_id == 20).rank_score == 4609
        assert next(r for r in rows if r.rank_game_id == 19).max_rank_score == 4894


def test_rank_fallback_does_not_replace_known_primary_ranks(monkeypatch):
    with RivalsClient() as client:
        result = {'rank_game_season': {'1001020': {
            'rank_game_id': 20, 'rank_score': 4700, 'max_rank_score': 5000}}}
        client._player_names[123] = 'A G N 1'
        monkeypatch.setattr(client.providers.tracker, 'request', lambda *a, **k: profile())
        client._enrich_ranks(result, 123)
        assert result['rank_game_season']['1001020']['rank_score'] == 4700
        assert result['rank_game_season']['1001020']['max_rank_score'] == 5000
        assert result['rank_summary']['current']['used_for_fallback'] is False
        assert result['rank_summary']['peak']['used_for_fallback'] is False


@pytest.mark.parametrize('verb', ['get', 'post'])
def test_exact_scope_stale_response_survives_restart(monkeypatch, tmp_path, verb):
    with RivalsClient(cache_dir=str(tmp_path)) as client:
        if verb == 'get':
            monkeypatch.setattr(client, '_get_json_live', lambda *a, **k: {'value': 7})
            assert client._get_json('/stats/tierlist', params={'rank': 'gold'})['value'] == 7
        else:
            monkeypatch.setattr(client, '_post_json_live', lambda *a, **k: [{'wins': 7}])
            assert client._post_json('/player/stats/maps', {'uid': 123, 'season': 20})[0]['wins'] == 7
    with RivalsClient(cache_dir=str(tmp_path)) as client:
        if verb == 'get':
            monkeypatch.setattr(client, '_get_json_live', offline)
            result = client._get_json('/stats/tierlist', params={'rank': 'gold'})
            assert result['value'] == 7 and result['provider_metadata']['fallback']['stale'] is True
            with pytest.raises(RivalsDataHTTPError):
                client._get_json('/stats/tierlist', params={'rank': 'diamond'})
        else:
            monkeypatch.setattr(client, '_post_json_live', offline)
            result = client._post_json('/player/stats/maps', {'uid': 123, 'season': 20})
            assert result[0]['wins'] == 7 and result[0]['provider_metadata']['fallback']['stale'] is True
            with pytest.raises(RivalsDataHTTPError):
                client._post_json('/player/stats/maps', {'uid': 123, 'season': 19})


def test_stale_cache_respects_expiry_and_explicit_privacy(monkeypatch):
    with RivalsClient(stale_cache_ttl=10) as client:
        clock = [1000.0]
        monkeypatch.setattr('rivals_api.resilience.time.time', lambda: clock[0])
        monkeypatch.setattr(client, '_post_json_live', lambda *a, **k: {'games': 7})
        client._post_json('/player/stats/maps', {'uid': 123})
        monkeypatch.setattr(client, '_post_json_live', offline)
        clock[0] += 11
        with pytest.raises(RivalsDataHTTPError):
            client._post_json('/player/stats/maps', {'uid': 123})
        clock[0] -= 11
        def private(*a, **k):
            raise PrivacyError('explicitly private endpoint')
        monkeypatch.setattr(client, '_post_json_live', private)
        with pytest.raises(PrivacyError):
            client._post_json('/player/stats/maps', {'uid': 123})


def test_stale_status_and_history_are_never_returned(monkeypatch):
    with RivalsClient() as client:
        monkeypatch.setattr(client, '_post_json_live', lambda *a, **k: {'matches': [], 'status': 'playing'})
        for path in ('/player/matches/cached', '/player/status', '/live'):
            client._post_json(path, {'uid': 123})
        monkeypatch.setattr(client, '_post_json_live', offline)
        for path in ('/player/matches/cached', '/player/status', '/live'):
            with pytest.raises(RivalsDataHTTPError):
                client._post_json(path, {'uid': 123})


def test_cached_profile_does_not_claim_live_status(monkeypatch):
    with RivalsClient() as client:
        monkeypatch.setattr(client, '_post_json_live', lambda *a, **k: {'name': 'test', 'status': {'battle_id': 'old'}})
        client._post_json('/player', {'uid': 123})
        monkeypatch.setattr(client, '_post_json_live', offline)
        result = client._post_json('/player', {'uid': 123})
        assert result['name'] == 'test' and 'status' not in result


def test_private_summary_data_is_kept_with_explicit_warning(monkeypatch):
    with RivalsClient() as client:
        stats = PlayerStats(client, 123)
        monkeypatch.setattr(stats, '_post', offline)
        monkeypatch.setattr(client, '_tracker_path', lambda uid: '/profile/test')
        monkeypatch.setattr(client.providers.rt, 'request', lambda *a, **k: {
            'player': {'_id': 123}, 'visibility': {'career_stats': False},
            'stats': {'ranked_matches': 10, 'ranked_matches_wins': 6,
                      'unranked_matches': 5, 'unranked_matches_wins': 3},
            'heroes_ranked': {'1055': {'matches': 10, 'win': 6}}})
        monkeypatch.setattr(client.providers.tracker, 'request', offline)
        result = stats.win_rate(season=20)
        assert result.win_rate_pct == 60
        assert result.metadata.private_profile is True
        assert 'inaccurate' in result.metadata.privacy_warning
        assert stats.hero_win_rates(season=20).data[0].wins == 6


def test_private_flags_in_tracker_do_not_discard_data(monkeypatch):
    with RivalsClient() as client:
        stats = PlayerStats(client, 123)
        monkeypatch.setattr(stats, '_post', offline)
        monkeypatch.setattr(client.providers.rt, 'request', offline)
        monkeypatch.setattr(client, '_tracker_path', lambda uid: '/profile/test')
        def tracker(path, params=None):
            if params is None:
                return deepcopy(profile())
            return [{'type': 'overview', 'attributes': params,
                     'stats': {'matchesPlayed': {'value': 10}, 'matchesWon': {'value': 6}}}]
        monkeypatch.setattr(client.providers.tracker, 'request', tracker)
        result = stats.win_rate(season=20)
        assert result.win_rate_pct == 60 and result.metadata.private_profile is True


def test_fresh_summary_outranks_stale_counts():
    from rivals_api.summary_rates import _select
    selected, metadata = _select([
        {'source': 'cached', 'counts_basis': 'career', 'games': 10, 'wins': 7, 'stale_snapshot': True},
        {'source': 'live', 'counts_basis': 'career', 'games': 12, 'wins': 8}])
    assert selected['source'] == 'live'
    assert metadata['uncertain'] is True


def test_stale_provider_profiles_do_not_verify_current_season(monkeypatch):
    with RivalsClient() as client:
        client._player_names[123] = 'A G N 1'
        monkeypatch.setattr(client.providers.tracker, '_request_live', lambda *a, **k: profile())
        stats = PlayerStats(client, 123)
        assert stats.analytics.seasons().data.currentSeason == 20
        monkeypatch.setattr(client.providers.tracker, '_request_live', offline)
        catalog = stats.analytics.seasons()
        assert catalog.data.currentSeason is None
        assert catalog.data.provider_metadata.fallback.stale is True


def test_refresh_never_substitutes_stale_provider_response(monkeypatch):
    with RivalsClient() as client:
        transport = client.providers.rt
        monkeypatch.setattr(transport, '_request_live', lambda *a, **k: {'value': 7})
        transport.request('/rank-distribution/data')
        monkeypatch.setattr(transport, '_request_live', offline)
        assert transport.request('/rank-distribution/data')['value'] == 7
        with pytest.raises(RivalsDataHTTPError):
            transport.request('/rank-distribution/data', refresh=True)
