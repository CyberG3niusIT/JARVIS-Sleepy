"""Provider failures never expose URLs, API keys or supplied locations."""

import logging
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.tools import get_weather


@pytest.mark.parametrize("method", ["_weather_current", "_weather_forecast",
                                    "_weather_tomorrow", "_weather_rain_check"])
def test_provider_exception_is_honest_and_content_free(monkeypatch, caplog, method):
    def fail(*args, **kwargs):
        raise RuntimeError("https://example.invalid/?appid=SYNTHETIC_SECRET&city=PRIVATE_LOCATION")

    monkeypatch.setattr("requests.get", fail)
    with caplog.at_level(logging.ERROR):
        result = getattr(get_weather, method)(1, 2, "PRIVATE_LOCATION", False)
    assert result == get_weather.WEATHER_UNAVAILABLE
    assert "SYNTHETIC_SECRET" not in caplog.text
    assert "PRIVATE_LOCATION" not in caplog.text


@pytest.mark.parametrize("last_day,next_day", [(datetime(2026, 9, 30), datetime(2026, 10, 1)),
                                               (datetime(2026, 12, 31), datetime(2027, 1, 1))])
def test_tomorrow_and_rain_check_use_full_date_across_month_and_year(monkeypatch, last_day, next_day):
    class Clock(datetime):
        @classmethod
        def now(cls):
            return last_day

        @classmethod
        def fromtimestamp(cls, value):
            return next_day

    data = {"list": [{"dt": 1, "main": {"temp": 40}, "pop": .8,
                      "weather": [{"main": "Rain", "description": "rain"}]}]}
    monkeypatch.setattr(get_weather, "datetime", Clock)
    monkeypatch.setattr("requests.get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: data))
    assert "Höchstwert 40" in get_weather._weather_tomorrow(1, 2, "Teststadt", False)
    assert "Regen erwartet" in get_weather._weather_rain_check(1, 2, "Teststadt", False)


def test_geocoding_uses_tls_and_does_not_log_failure_contents(monkeypatch, caplog):
    called = []

    def fail(url, **kwargs):
        called.append(url)
        raise RuntimeError("appid=SYNTHETIC_SECRET&city=PRIVATE_LOCATION")

    monkeypatch.setattr("requests.get", fail)
    with caplog.at_level(logging.ERROR):
        result = get_weather._resolve_location("PRIVATE_LOCATION")
    assert result == get_weather.WEATHER_UNAVAILABLE
    assert called == ["https://api.openweathermap.org/geo/1.0/direct"]
    assert "SYNTHETIC_SECRET" not in caplog.text
    assert "PRIVATE_LOCATION" not in caplog.text
