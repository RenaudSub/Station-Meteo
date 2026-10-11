"""Astronomy, daily date checks and download throttling."""
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch
import asyncio
import pytest
from custom_components.station_meteo.ephemeris import astronomy, parse_almanac, async_ephemeris


def sample(day):
    return f'''<script>{{"dateModified":"{day}"}}</script>
    <div class="hero-card"><span>Saint du jour</span><strong>Saint Test</strong></div>
    <div class="hero-card"><span>Citation</span><p>Une citation &amp; son auteur.</p></div>
    <div class="hero-card"><span>Dicton du jour</span><p>Un dicton de test.</p></div>'''


def test_parser_date_check_and_text_only():
    data = parse_almanac(sample('2026-10-11'), date(2026, 10, 11))
    assert data['quote'] == 'Une citation & son auteur.'
    assert data['saint'] == 'Saint Test'
    with pytest.raises(ValueError):
        parse_almanac(sample('2026-10-10'), date(2026, 10, 11))
    with pytest.raises(ValueError):
        parse_almanac('<script>{"dateModified":"2026-10-11"}</script>', date(2026, 10, 11))


def test_astronomy_observer_timezone_and_polar_night():
    hass = SimpleNamespace(config=SimpleNamespace(latitude=48.8566, longitude=2.3522, time_zone='Europe/Paris'))
    cfg = dict(latitude=42.627506, longitude=2.593331, altitude=247)
    sky = astronomy(hass, cfg, datetime(2026, 10, 11, 12, tzinfo=ZoneInfo('Europe/Paris')))
    assert sky['date'] == '2026-10-11'
    assert sky['sunrise'].endswith('+02:00')
    assert 7 <= datetime.fromisoformat(sky['sunrise']).hour <= 8
    assert datetime.fromisoformat(sky['sunrise']) < datetime.fromisoformat(sky['noon']) < datetime.fromisoformat(sky['sunset'])
    assert 0 <= sky['moon_illumination'] <= 100
    # Null coordinates select Home Assistant's location; zero is valid.
    other = astronomy(hass, {**cfg, 'latitude': None, 'longitude': None}, datetime(2026, 10, 11, 12, tzinfo=ZoneInfo('Europe/Paris')))
    assert other['sunrise'] != sky['sunrise']
    polar = astronomy(hass, {**cfg, 'latitude': 89}, datetime(2026, 12, 21, 12, tzinfo=ZoneInfo('Europe/Paris')))
    assert polar['sunrise'] is None and polar['sunset'] is None and polar['noon']


@pytest.mark.asyncio
async def test_cache_retry_and_disabled_make_no_requests():
    hass = SimpleNamespace()
    sky = {'date': '2026-10-11'}
    runtime = {'config': {'ephemeride_enabled': True}, 'almanac_cache': {'date': '2026-10-11', 'saint': 'Test'}}
    with patch('custom_components.station_meteo.ephemeris.astronomy', return_value=sky), patch('custom_components.station_meteo.ephemeris.async_get_clientsession') as session:
        assert (await async_ephemeris(hass, runtime))['almanac']['saint'] == 'Test'
        runtime['almanac_cache']['date'] = '2026-10-10'
        runtime['almanac_retry'] = asyncio.get_running_loop().time() + 60
        result = await async_ephemeris(hass, runtime)
        assert result['almanac'] is None and result['almanac_status'] == 'unavailable'
        runtime['config']['ephemeride_enabled'] = False
        assert (await async_ephemeris(hass, runtime))['almanac_status'] == 'disabled'
        session.assert_not_called()


def test_next_moon_events_cross_dst_and_roll_forward():
    hass=SimpleNamespace(config=SimpleNamespace(latitude=42.627506,longitude=2.593331,time_zone='Europe/Paris'))
    cfg={'altitude':247}
    sky=astronomy(hass,cfg,datetime(2026,10,11,13,55,tzinfo=ZoneInfo('Europe/Paris')))
    full=datetime.fromisoformat(sky['next_full_moon']);new=datetime.fromisoformat(sky['next_new_moon'])
    assert full.date()==date(2026,10,26) and full.hour==5 and full.utcoffset().total_seconds()==3600
    assert new.date()==date(2026,11,9) and new.hour==8
    later=astronomy(hass,cfg,datetime(2026,11,10,12,tzinfo=ZoneInfo('Europe/Paris')))
    assert later['next_new_moon']>sky['next_new_moon']
