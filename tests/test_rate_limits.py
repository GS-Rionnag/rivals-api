from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import format_datetime
from threading import Event
from types import SimpleNamespace

import pytest

from rivals_api import RivalsClient, RivalsDataHTTPError
from rivals_api.rate_limits import RateGate, retry_after


@pytest.fixture
def clock(monkeypatch):
    now, sleeps = [100.0], []
    monkeypatch.setattr('rivals_api.rate_limits.time.monotonic', lambda: now[0])

    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr('rivals_api.rate_limits.time.sleep', sleep)
    return now, sleeps


def test_pacing_and_cooldown_are_shared_across_client_restarts(monkeypatch, clock):
    now, sleeps = clock
    calls = []
    with RivalsClient() as first, RivalsClient() as second:
        assert first._rate_gate is second._rate_gate

        def success(*args, **kwargs):
            calls.append(now[0])
            return SimpleNamespace(status_code=200)

        monkeypatch.setattr(first.session, 'get', success)
        monkeypatch.setattr(second.session, 'get', success)
        first._request_with_gateway_retries(first.session.get, '/player')
        second._request_with_gateway_retries(second.session.get, '/player')
        assert calls == [100, 101] and sleeps == [1]
        monkeypatch.setattr(first.session, 'get', lambda *a, **k: SimpleNamespace(
            status_code=429, headers={'Retry-After': '45'}))
        with pytest.raises(RivalsDataHTTPError) as error:
            first._request_with_gateway_retries(first.session.get, '/player')
        assert error.value.retry_after == 45 and error.value.status_code == 429
    with RivalsClient() as restarted:
        monkeypatch.setattr(restarted.session, 'get', success)
        with pytest.raises(RivalsDataHTTPError, match='retry after 45'):
            restarted._request_with_gateway_retries(restarted.session.get, '/another')
        assert calls == [100, 101]
        now[0] += 45
        restarted._request_with_gateway_retries(restarted.session.get, '/another')
        assert len(calls) == 3


def test_retry_after_dates_and_invalid_values(monkeypatch):
    monkeypatch.setattr('rivals_api.rate_limits.time.time', lambda: 1000)
    date = format_datetime(datetime.fromtimestamp(1075, timezone.utc), usegmt=True)
    assert retry_after(date) == 75
    assert retry_after('12.5') == 12.5
    for value in ('bad', '-3', 'nan', 'inf', None):
        assert retry_after(value) is None


def test_fallback_cooldown_grows_and_success_resets_it(clock):
    now, _ = clock
    gate = RateGate('test')
    for delay in (30, 60, 120, 240, 300):
        with pytest.raises(RivalsDataHTTPError) as error:
            gate.run(lambda: SimpleNamespace(status_code=429, headers={}))
        assert error.value.retry_after == delay
        now[0] += delay
    gate.run(lambda: SimpleNamespace(status_code=200))
    with pytest.raises(RivalsDataHTTPError) as error:
        gate.run(lambda: SimpleNamespace(status_code=429))
    assert error.value.retry_after == 30


def test_browser_429_uses_shared_guard_and_retry_header(clock):
    now, _ = clock
    with RivalsClient() as client:
        page = SimpleNamespace(evaluate=lambda *a: {
            'status': 429, 'text': '{}', 'headers': {'Retry-After': '90'}})
        with pytest.raises(RivalsDataHTTPError) as error:
            client._paced_browser_evaluate(page, '', {})
        assert error.value.retry_after == 90
        page.evaluate = lambda *a: pytest.fail('Browser request during cooldown')
        with pytest.raises(RivalsDataHTTPError):
            client._paced_browser_evaluate(page, '', {})
        # Providers have independent budgets.
        assert client.providers.tracker._rate_gate.blocked_until <= now[0]


def test_concurrent_requests_observe_first_response_cooldown():
    gate, entered, release = RateGate('test'), Event(), Event()
    calls = []

    def upstream():
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return SimpleNamespace(status_code=429, headers={'Retry-After': '30'})

    def request():
        with pytest.raises(RivalsDataHTTPError):
            gate.run(upstream)

    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(request)
        assert entered.wait(3)
        second, third = pool.submit(request), pool.submit(request)
        release.set()
        for future in (first, second, third):
            future.result(timeout=3)
    assert calls == [1]


def test_provider_cached_reads_still_work_during_cooldown(monkeypatch, clock):
    with RivalsClient() as client:
        transport = client.providers.rt
        calls = []

        def get(*args, **kwargs):
            calls.append(1)
            return SimpleNamespace(status_code=200, text='{"value":1}')

        monkeypatch.setattr(transport.session, 'get', get)
        assert transport.request('/cached') == {'value': 1}
        monkeypatch.setattr(transport.session, 'get', lambda *a, **k: SimpleNamespace(status_code=429))
        with pytest.raises(RivalsDataHTTPError):
            transport.request('/limited')
        assert transport.request('/cached') == {'value': 1}
        with pytest.raises(RivalsDataHTTPError):
            transport.request('/cached', refresh=True)
        assert calls == [1]


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf'), '1'])
def test_invalid_settings_are_rejected(value):
    for name in ('request_interval', 'rate_limit_cooldown'):
        with pytest.raises(ValueError, match=name):
            RivalsClient(**{name: value})
