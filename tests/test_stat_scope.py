from types import SimpleNamespace

import pytest

from rivals_api import DataModel, RivalsDataHTTPError
from rivals_api.extensions import PlayerAnalytics
from rivals_api.stat_scope import resolve_season


def resource(tracker_value=None, rt_value=None, *, tracker_error=False, rt_error=False):
    calls = []

    def seasons():
        calls.append("tracker")
        if tracker_error:
            raise RivalsDataHTTPError("profile unavailable")
        return DataModel({"data": {"currentSeason": tracker_value, "defaultSeason": 19}})

    def request(path):
        calls.append(path)
        if rt_error:
            raise RivalsDataHTTPError("global stats unavailable")
        return {"season": rt_value}

    return SimpleNamespace(analytics=SimpleNamespace(seasons=seasons),
                           _client=SimpleNamespace(providers=SimpleNamespace(
                               rt=SimpleNamespace(request=request)))), calls


@pytest.mark.parametrize("selector", [None, "current"])
@pytest.mark.parametrize("value", [20, "20"])
def test_current_accepts_numeric_metadata(selector, value):
    stats, calls = resource(value)
    assert resolve_season(stats, selector) == 20
    assert calls == ["tracker"]


@pytest.mark.parametrize("value", [None, True, 0, -1, 20.5, "invalid"])
def test_invalid_tracker_current_uses_global_season(value):
    stats, calls = resource(value, "20")
    assert resolve_season(stats, "current") == 20
    assert calls == ["tracker", "/heroes/stats"]


def test_tracker_outage_uses_global_season():
    stats, _ = resource(rt_value=20, tracker_error=True)
    assert resolve_season(stats, None) == 20


def test_no_verified_current_never_uses_default_or_all():
    stats, _ = resource(rt_error=True)
    with pytest.raises(ValueError, match="Cannot verify the current season.*positive season ID"):
        resolve_season(stats, None)


@pytest.mark.parametrize("selector", [1, 19, 20, "all"])
def test_explicit_season_bypasses_current_detection(selector):
    stats, calls = resource(tracker_error=True, rt_error=True)
    assert resolve_season(stats, selector) == selector
    assert calls == []


@pytest.mark.parametrize("selector", [True, False, 0, -1, 20.5, "20", "S10", "unknown"])
def test_invalid_explicit_seasons_fail_without_requests(selector):
    stats, calls = resource()
    with pytest.raises(ValueError, match="positive ID, 'current', or 'all'"):
        resolve_season(stats, selector)
    assert calls == []


@pytest.mark.parametrize("body", [None, [], {}, {"metadata": None}, {"metadata": []}])
def test_malformed_tracker_catalog_remains_available_for_resolution_fallback(body):
    client = SimpleNamespace(_tracker_path=lambda uid: "/profile/GS-4",
                             providers=SimpleNamespace(tracker=SimpleNamespace(
                                 request=lambda path: body)))
    catalog = PlayerAnalytics(client, 691218686).seasons()
    assert catalog.data.currentSeason is None
