"""Local astronomy and offline daily data."""
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch
import asyncio
import pytest
from custom_components.station_meteo.ephemeris import astronomy, async_ephemeris
from custom_components.station_meteo.almanac_data import LocalAlmanac


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


def test_next_moon_events_cross_dst_and_roll_forward():
    hass=SimpleNamespace(config=SimpleNamespace(latitude=42.627506,longitude=2.593331,time_zone='Europe/Paris'))
    cfg={'altitude':247}
    sky=astronomy(hass,cfg,datetime(2026,10,11,13,55,tzinfo=ZoneInfo('Europe/Paris')))
    full=datetime.fromisoformat(sky['next_full_moon']);new=datetime.fromisoformat(sky['next_new_moon'])
    assert full.date()==date(2026,10,26) and full.hour==5 and full.utcoffset().total_seconds()==3600
    assert new.date()==date(2026,11,9) and new.hour==8
    later=astronomy(hass,cfg,datetime(2026,11,10,12,tzinfo=ZoneInfo('Europe/Paris')))
    assert later['next_new_moon']>sky['next_new_moon']


@pytest.mark.asyncio
async def test_ephemeris_local_day_rollover_disabled_and_no_network(tmp_path):
    service=LocalAlmanac(tmp_path/'almanac');service.initialize()
    hass=SimpleNamespace(async_add_executor_job=lambda fn,*args:asyncio.to_thread(fn,*args))
    runtime={'config':{'ephemeride_enabled':True},'almanac':service}
    for value in ('2026-12-31','2027-01-01','2028-02-29','2028-03-01'):
        with patch('custom_components.station_meteo.ephemeris.astronomy',return_value={'date':value}):
            result=await async_ephemeris(hass,runtime)
            assert result['almanac']['date']==value and result['almanac']['local']
            assert all(result['almanac'][key] for key in ('saint','quote','saying'))
    runtime['config']['ephemeride_enabled']=False
    with patch('custom_components.station_meteo.ephemeris.astronomy',return_value={'date':'2026-10-15'}),patch.object(service,'daily',side_effect=AssertionError('must not read')):
        assert (await async_ephemeris(hass,runtime))['almanac_status']=='disabled'
