import pytest

from rivals_api import Match, MatchHistory, RivalsClient, RivalsDataHTTPError
from rivals_api.cache import MatchCache, incremental_history
from rivals_api.resources import PlayerMatches, PlayerStats


def test_normal_shares_summary_without_history(monkeypatch):
    with RivalsClient(enrich=False) as client:
        calls = []

        def post(path, **kwargs):
            calls.append(path)
            if path.endswith('/heroes'):
                return [{'hero_id': 1055, 'competitive': {'games': 10, 'wins': 7},
                         'quickplay': {'games': 6, 'wins': 2}}]
            if path.endswith('/maps'):
                return [{'competitive': {'games': 10, 'wins': 7},
                         'quickplay': {'games': 6, 'wins': 2}}]
            return {}

        stats = PlayerStats(client, 123)
        monkeypatch.setattr(stats, '_post', post)
        monkeypatch.setattr(PlayerMatches, 'fetch', lambda *a, **k: pytest.fail('History requested'))
        monkeypatch.setattr(client.matches, 'get', lambda *a, **k: pytest.fail('Detail requested'))
        overall = stats.win_rate(season=20)
        heroes = stats.hero_win_rates(season=20)
        classes = stats.class_win_rates(season=20)
        assert (overall.games, overall.wins, overall.win_rate_pct) == (16, 9, 56.25)
        assert heroes.data[0].wins == classes.data[0].wins == 9
        assert overall.metadata.coverage.history_requested is False
        assert len(calls) == 3


def test_provider_disagreement_keeps_intact_counts():
    from rivals_api.summary_rates import _select, counts
    selected, metadata = _select([
        {'source': 'a', 'counts_basis': 'career', 'games': 100, 'wins': 60},
        {'source': 'b', 'counts_basis': 'career', 'games': 30, 'wins': 10},
    ])
    assert selected['games'] == 100 and selected['wins'] == 60
    assert metadata['uncertain'] is True
    assert counts(2.5, 1.5)['losses'] == 1
    assert counts(0, 0) is not None
    assert counts(2, 3) is None
    assert counts(float('nan'), 0) is None


def row(identifier, timestamp=100):
    return {'match_uid': identifier, 'timestamp': timestamp, 'season': 20, 'game_mode_id': 2}


def test_real_pagination_stops_at_cached_boundary_and_survives_restart(monkeypatch, tmp_path):
    calls = []
    pages = {None: {'matches': [row('newest', 300)], 'next_cursor': 'older'},
             'older': {'matches': [row('old', 200)], 'next_cursor': None}}

    def post(self, path, **kwargs):
        calls.append(kwargs['cursor'])
        return pages[kwargs['cursor']]

    monkeypatch.setattr(PlayerMatches, '_post', post)
    with RivalsClient(enrich=False, cache_dir=str(tmp_path)) as client:
        first = PlayerMatches(client, 123).fetch(limit='all', season=20, incremental=True)
        assert len(first.matches) == 2
    assert calls == [None, 'older']
    calls.clear()
    pages[None] = {'matches': [row('added', 400), row('newest', 300)], 'next_cursor': 'older'}
    with RivalsClient(enrich=False, cache_dir=str(tmp_path)) as client:
        second = PlayerMatches(client, 123).fetch(limit='all', season=20, incremental=True)
        assert {m.match_uid for m in second.matches} == {'added', 'newest', 'old'}
        assert second.provider_metadata.cache.matches_reused == 2
        assert second.provider_metadata.cache.provider_cutoffs == ['rivalsdata']
    assert calls == [None]


def test_interrupted_scan_cannot_establish_stopping_frontier(monkeypatch):
    calls, broken = [], [True]

    def post(self, path, **kwargs):
        calls.append(kwargs['cursor'])
        if kwargs['cursor'] is None:
            return {'matches': [row('newest', 300)], 'next_cursor': 'older'}
        if broken[0]:
            raise RivalsDataHTTPError('offline')
        return {'matches': [row('old', 200)], 'next_cursor': None}

    monkeypatch.setattr(PlayerMatches, '_post', post)
    with RivalsClient(enrich=False) as client:
        resource = PlayerMatches(client, 123)
        first = resource.fetch(limit='all', season=20, incremental=True)
        assert first.provider_metadata.errors
        broken[0] = False
        calls.clear()
        second = resource.fetch(limit='all', season=20, incremental=True)
        assert len(second.matches) == 2
        assert calls == [None, 'older']


def test_each_provider_has_its_own_boundary(monkeypatch):
    requests = []

    def history(resource, **kwargs):
        requests.append(kwargs['stop_at'])
        return MatchHistory({'matches': [row('a'), row('b')], 'next_cursor': None, 'provider_metadata': {
            'sources': ['rivalsdata', 'tracker'], 'errors': [], 'checkpoints': {
                'rivalsdata': {'ids': ['a'], 'complete': True, 'ordered': True},
                'tracker': {'ids': ['b'], 'complete': False, 'ordered': True}}}})

    monkeypatch.setattr('rivals_api.history.fetch_history', history)
    with RivalsClient() as client:
        resource = PlayerMatches(client, 123)
        incremental_history(resource, season=20)
        incremental_history(resource, season=20)
        assert requests == [{}, {'rivalsdata': {'a'}}]


def test_out_of_order_pages_disable_cutoff(monkeypatch):
    calls = []

    def post(self, path, **kwargs):
        calls.append(kwargs['cursor'])
        if kwargs['cursor'] is None:
            return {'matches': [row('a', 100), row('b', 200)], 'next_cursor': 'tail'}
        return {'matches': [row('c', 50)], 'next_cursor': None}

    monkeypatch.setattr(PlayerMatches, '_post', post)
    with RivalsClient(enrich=False) as client:
        resource = PlayerMatches(client, 123)
        resource.fetch(limit='all', season=20, incremental=True)
        calls.clear()
        resource.fetch(limit='all', season=20, incremental=True)
        assert calls == [None, 'tail']


def test_persistent_evidence_survives_memory_eviction(tmp_path):
    store = MatchCache(tmp_path)
    for index in range(520):
        store.put('details', index, {'match_uid': str(index)})
    assert len(store.memory) <= 512
    store.close()
    restarted = MatchCache(tmp_path)
    assert restarted.get('details', 0) == {'match_uid': '0'}
    assert restarted.get('details', 519) == {'match_uid': '519'}
    restarted.close()


def test_precise_overall_uses_details_without_hero_playtime(monkeypatch):
    from rivals_api.client import _MATCH_DETAIL_CACHE
    calls = []
    monkeypatch.setattr(PlayerMatches, 'fetch', lambda *a, **k: MatchHistory({
        'matches': [row('a'), row('b')], 'provider_metadata': {'sources': [], 'errors': []}}))
    for attempt in range(2):
        with RivalsClient(enrich=False) as client:
            def get(identifier):
                calls.append(identifier)
                return Match({'match_uid': identifier, 'teams': [{'players': [{
                    'uid': 123, 'is_win': identifier == 'a'}]}], 'provider_metadata': {
                        'sources': ['rivalsdata'], 'evidence': {'rivalsdata': {'complete': True}}}})
            monkeypatch.setattr(client.matches, 'get', get)
            result = PlayerStats(client, 123).win_rate(season=20, mode='competitive', method='precise')
            assert result.games == 2 and result.win_rate_pct == 50
        _MATCH_DETAIL_CACHE.clear()
    assert calls == ['a', 'b']


def test_tracker_fractional_roles_and_private_rt_fallback(monkeypatch):
    with RivalsClient() as client:
        stats = PlayerStats(client, 123)
        monkeypatch.setattr(stats, '_post', lambda *a, **k: [])
        monkeypatch.setattr(client, '_tracker_path', lambda uid: '/profile/test')
        monkeypatch.setattr(client.providers.rt, 'request', lambda *a, **k: {
            'player': {'_id': 123}, 'visibility': {'career_stats': False},
            'stats': {'ranked_matches': 100, 'ranked_matches_wins': 99}})

        def tracker(path, params=None):
            if params is None:
                return {'metadata': {}}
            attributes = {'season': 20, 'mode': 'competitive'}
            return [{'type': kind, 'attributes': {**attributes, **extra}, 'stats': {
                'matchesPlayed': {'value': games}, 'matchesWon': {'value': wins}}}
                    for kind, extra, games, wins in [
                        ('overview', {}, 10, 6), ('hero', {'heroId': 1055}, 2.5, 1.5),
                        ('hero-role', {'roleId': 'duelist'}, 3.5, 2.5)]]

        monkeypatch.setattr(client.providers.tracker, 'request', tracker)
        overall = stats.win_rate(season=20, mode='competitive')
        hero = stats.hero_win_rates(season=20, mode='competitive').data[0]
        role = stats.class_win_rates(season=20, mode='competitive').data[0]
        assert overall.games == 10 and overall.wins == 6
        assert overall.metadata.selection_uncertain is True
        assert hero.games == 2.5 and hero.wins == 1.5
        assert role.games == 3.5 and role.wins == 2.5


def test_missing_mode_does_not_report_partial_overall_as_complete(monkeypatch):
    with RivalsClient(enrich=False) as client:
        stats = PlayerStats(client, 123)
        monkeypatch.setattr(stats, '_post', lambda path, **k: [
            {'hero_id': 1055, 'competitive': {'games': 0, 'wins': 0}}]
            if path.endswith('/heroes') else [
                {'competitive': {'games': 0, 'wins': 0}}] if path.endswith('/maps') else {})
        result = stats.win_rate(season=20)
        assert result.games is None and result.win_rate_pct is None
        assert result.metadata.coverage.missing_overall_modes == ['quickplay']
        assert stats.hero_win_rates(season=20).data[0].win_rate_pct is None


@pytest.mark.parametrize('method', ['typo', '', 1])
def test_invalid_method_fails_before_network(monkeypatch, method):
    with RivalsClient() as client:
        monkeypatch.setattr(client, '_post_json', lambda *a, **k: pytest.fail('Network requested'))
        for name in ('win_rate', 'hero_win_rates', 'class_win_rates'):
            with pytest.raises(ValueError, match='method'):
                getattr(PlayerStats(client, 123), name)(method=method)


def test_lifetime_tracker_uses_verified_catalog_without_history(monkeypatch):
    with RivalsClient() as client:
        stats, calls = PlayerStats(client, 123), []
        monkeypatch.setattr(stats, '_post', lambda *a, **k: [])
        monkeypatch.setattr(client, '_tracker_path', lambda uid: '/profile/test')
        monkeypatch.setattr(client.providers.rt, 'request', lambda *a, **k: pytest.fail('Unscoped RT requested'))

        def tracker(path, params=None):
            if params is None:
                return {'metadata': {'seasons': [{'id': 19}, {'id': 20}]}}
            calls.append(params)
            return [{'type': 'overview', 'attributes': params,
                     'stats': {'matchesPlayed': {'value': 10}, 'matchesWon': {'value': 6}}}]

        monkeypatch.setattr(client.providers.tracker, 'request', tracker)
        monkeypatch.setattr(PlayerMatches, 'fetch', lambda *a, **k: pytest.fail('History requested'))
        result = stats.win_rate(season='all', mode='competitive')
        assert result.games == 20 and result.wins == 12
        assert [params['season'] for params in calls] == [19, 20]


def test_cache_storage_failure_keeps_memory_evidence(tmp_path):
    blocked = tmp_path / 'file'
    blocked.write_text('not a directory')
    store = MatchCache(blocked)
    store.put('details', 'a', {'value': 1})
    assert store.get('details', 'a') == {'value': 1}
    assert store.errors
    store.close()


def test_failed_normal_lookup_does_not_repeat_rate_limited_requests(monkeypatch):
    calls = []
    clock = [100.0]
    monkeypatch.setattr('rivals_api.summary_rates.time.monotonic', lambda: clock[0])
    with RivalsClient(enrich=False) as client:
        stats = PlayerStats(client, 123)

        def limited(path, **kwargs):
            calls.append(path)
            raise RivalsDataHTTPError('RivalsData rate limited the request (HTTP 429)')

        monkeypatch.setattr(stats, '_post', limited)
        for name in ('win_rate', 'hero_win_rates', 'class_win_rates'):
            with pytest.raises(RivalsDataHTTPError, match='429'):
                getattr(stats, name)(season=20)
        assert calls == ['/player/stats/heroes']
        clock[0] += 6
        with pytest.raises(RivalsDataHTTPError, match='429'):
            stats.win_rate(season=20)
        assert len(calls) == 2


def test_rate_limited_primary_does_not_block_other_summary_sources(monkeypatch):
    with RivalsClient() as client:
        stats, calls = PlayerStats(client, 123), []

        def limited(path, **kwargs):
            calls.append(path)
            raise RivalsDataHTTPError('HTTP 429')

        monkeypatch.setattr(stats, '_post', limited)
        monkeypatch.setattr(client, '_tracker_path', lambda uid: '/profile/test')
        monkeypatch.setattr(client.providers.tracker, 'request', lambda *a, **k: [])
        monkeypatch.setattr(client.providers.rt, 'request', lambda *a, **k: {
            'player': {'_id': 123}, 'stats': {
                'ranked_matches': 10, 'ranked_matches_wins': 6,
                'unranked_matches': 5, 'unranked_matches_wins': 3}})
        result = stats.win_rate(season=20)
        assert result.win_rate_pct == 60
        assert calls == ['/player/stats/heroes']
