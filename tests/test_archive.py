"""Real persistent archive, counter edge cases and local calendar aggregation."""
from datetime import datetime, date, timedelta, timezone
from copy import deepcopy
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch, AsyncMock
import asyncio
import sqlite3
import pytest
from homeassistant.core import State, HomeAssistant
from custom_components.station_meteo.archive import HourArchive, ArchiveService, Source, boundaries, period_range, sources
from custom_components.station_meteo.const import DEFAULT_CONFIG

UTC = timezone.utc
ZONE = 'Europe/Paris'

def stamp(text): return datetime.fromisoformat(text).timestamp()
def state(value, t, unit='mm'): return State('sensor.rain', str(value), {'unit_of_measurement':unit}, last_updated=datetime.fromtimestamp(t,UTC))

def archive(tmp_path):
    store = HourArchive(tmp_path/'history.sqlite3');store.initialize();return store

def rows(store, source, start, end): return store.read(source,start,end)[0]

def test_weighted_mean_extrema_and_reopen(tmp_path):
    a=archive(tmp_path);s=Source('temperature','sensor.temp');t=stamp('2026-10-16T10:00:00+02:00')
    a.import_series(s,[state(10,t,'°C'),state(30,t+900,'°C')],t,t+3600,ZONE)
    data=rows(a,s,t,t+3600);assert len(data)==1
    assert data[0][1]/data[0][2]==25
    assert data[0][2:5]==(3600,10,30)
    b=HourArchive(a.path);b.initialize();assert rows(b,s,t,t+3600)==data
    a.import_series(s,[state(10,t,'°C'),state(30,t+900,'°C')],t,t+3600,ZONE)
    assert rows(a,s,t,t+3600)==data


def test_rain_resets_cross_hour_and_no_double_import(tmp_path):
    a=archive(tmp_path);s=Source('rain','sensor.rain','counter');t=stamp('2026-10-16T10:00:00+02:00')
    series=[state(10,t),state(10.3,t+1800),state(10.4,t+3660),state(0,t+4500),state(.2,t+5400)]
    a.import_series(s,series,t,t+7200,ZONE)
    data=rows(a,s,t,t+7200);assert data[0][5]==pytest.approx(.3);assert data[1][5]==pytest.approx(.3)
    assert sum(r[2] for r in data)==7200
    b=HourArchive(a.path);b.initialize();b.import_series(s,series,t,t+7200,ZONE)
    assert rows(b,s,t,t+7200)==data


def test_restart_import_extends_partial_counter_without_duplicate_delta(tmp_path):
    a=archive(tmp_path);s=Source('rain','sensor.rain','counter');t=stamp('2026-10-16T10:00:00+02:00')
    initial=[state(5,t),state(5.1,t+900)]
    a.import_series(s,initial,t,t+1800,ZONE);assert rows(a,s,t,t+3600)[0][5]==pytest.approx(.1)
    b=HourArchive(a.path);b.initialize()
    b.import_series(s,initial+[state(5.3,t+2700)],t,t+3600,ZONE)
    r=rows(b,s,t,t+3600)[0];assert r[5]==pytest.approx(.3);assert r[2]==3600


def test_missing_data_is_partial_not_zero_and_negative_counter_rejected(tmp_path):
    a=archive(tmp_path);s=Source('rain','sensor.rain','counter');t=stamp('2026-10-16T10:00:00+02:00')
    a.import_series(s,[],t,t+3600,ZONE);assert rows(a,s,t,t+3600)==[]
    a.import_series(s,[state(0,t+1800),state('unavailable',t+2400),state(0,t+3000)],t,t+3600,ZONE)
    r=rows(a,s,t,t+3600)[0];assert r[5]==0;assert r[2]==600
    assert s.value(state(-1,t)) is None
    assert s.value(state('nan',t)) is None


def test_long_constant_history_and_live_gaps(tmp_path):
    a=archive(tmp_path);s=Source('rain','sensor.rain','counter');t=stamp('2026-10-16T00:00:00+02:00')
    a.import_series(s,[state(14,t-86400)],t,t+86400,ZONE)
    assert len(rows(a,s,t,t+86400))==24
    assert sum(r[5] for r in rows(a,s,t,t+86400))==0
    a.feed(s,t+86400,14,ZONE);a.feed(s,t+86460,14.1,ZONE)
    a.feed(s,t+90000,15,ZONE) # outage: no fabricated quantity across this gap
    r=rows(a,s,t+86400,t+93600)[0];assert r[2]==60;assert r[5]==pytest.approx(.1)


def test_counter_exact_boundary_and_rate_integration(tmp_path):
    a=archive(tmp_path);s=Source('rain','sensor.rain','counter');t=stamp('2026-10-16T10:00:00+02:00')
    a.import_series(s,[state(0,t),state(.2,t+3600)],t,t+7200,ZONE)
    rr=rows(a,s,t,t+7200);assert [r[5] for r in rr]==[.2,0]
    rate=Source('rain','sensor.rate','rate');a.import_series(rate,[state(1.2,t,'mm/h')],t,t+7200,ZONE)
    assert sum(r[5] for r in rows(a,rate,t,t+7200))==pytest.approx(2.4)


def test_local_calendar_leap_year_dst_and_source_isolation(tmp_path):
    a=archive(tmp_path);s=Source('temperature','sensor.a')
    for day,hours in [(date(2026,3,29),23),(date(2026,10,25),25)]:
        start,end=boundaries(day,ZONE);assert end-start==hours*3600
        a.import_series(s,[state(20,start,'°C')],start,end,ZONE)
        data=rows(a,s,start,end);assert len(data)==hours
        assert sum(r[2] for r in data)==hours*3600
        assert rows(a,Source('temperature','sensor.b'),start,end)==[]
    first,last,start,end=period_range(date(2028,2,29),'month',ZONE)
    assert first==date(2028,2,1) and last==date(2028,3,1) and end-start==29*86400


def test_units_estimated_source_and_invalid_values():
    t=0
    assert Source('temperature','sensor.t').value(state(68,t,'°F'))==pytest.approx(20)
    assert Source('rain','sensor.r','counter').value(state(1,t,'in'))==25.4
    assert Source('pressure','sensor.p').value(state(100000,t,'Pa'))==1000
    assert Source('wind_speed','sensor.w').value(state(36,t,'km/h'))==10
    assert Source('irradiance','sensor.s').value(state(.5,t,'kW/m²'))==500
    assert Source('irradiance','sensor.l','lux',100).value(state(50,t,'klx'))==500
    cfg=deepcopy(DEFAULT_CONFIG);cfg.update(estimate_irradiance=True,lux_factor=100,entities={'illuminance':'sensor.l','rain_total':'sensor.r'})
    result=sources(cfg);assert {s.role for s in result}=={'rain','irradiance'}
    assert result[-1].key!=Source('irradiance','sensor.l','lux',126.7).key


@pytest.mark.asyncio
async def test_service_query_week_month_partial_and_durable_relaunch(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone=ZONE
    cfg=deepcopy(DEFAULT_CONFIG);cfg['entities']={'rain_total':'sensor.rain','temperature':'sensor.temp','wind_speed':'sensor.wind','wind_gust':'sensor.gust'}
    service=ArchiveService(hass,{'config':cfg});await hass.async_add_executor_job(service.store.initialize)
    day=date(2026,10,10);start,end=boundaries(day,ZONE)
    rain=Source('rain','sensor.rain','counter');temp=Source('temperature','sensor.temp')
    await hass.async_add_executor_job(service.store.import_series,rain,[state(5,start),state(5.3,start+3600)],start,end,ZONE)
    await hass.async_add_executor_job(service.store.import_series,temp,[state(10,start,'°C'),state(20,start+43200,'°C')],start,end,ZONE)
    result=await service.query('rain',day,'hour');assert len(result['points'])==24;assert result['summary']['value']==.3;assert not result['summary']['partial']
    assert result['points'][0]['value']==.3
    weekly=await service.query('rain',day,'week');assert len(weekly['points'])==7;assert weekly['summary']['partial'];assert weekly['points'][0]['value'] is None;assert weekly['summary']['value']==.3
    monthly=await service.query('temperature',day,'month');assert len(monthly['points'])==31;assert monthly['summary']['value']==15;assert monthly['summary']['min']==10;assert monthly['summary']['max']==20
    relaunched=ArchiveService(hass,{'config':cfg});await hass.async_add_executor_job(relaunched.store.initialize)
    assert (await relaunched.query('rain',day,'hour'))['summary']['value']==.3
    await hass.async_stop(force=True)


@pytest.mark.asyncio
async def test_collection_without_panel_with_state_events_and_unload(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone=ZONE
    cfg=deepcopy(DEFAULT_CONFIG);cfg['entities']={'rain_total':'sensor.rain','temperature':'sensor.temp'}
    hass.states.async_set('sensor.rain','3',{'unit_of_measurement':'mm'})
    hass.states.async_set('sensor.temp','20',{'unit_of_measurement':'°C'})
    service=ArchiveService(hass,{'config':cfg});await service.start()
    await hass.async_block_till_done()
    # Recorded state events enter the queue without an open web panel.
    hass.states.async_set('sensor.rain','3.1',{'unit_of_measurement':'mm'})
    hass.states.async_set('sensor.temp','22',{'unit_of_measurement':'°C'})
    await hass.async_block_till_done()
    await service.tick(datetime.now(UTC)+timedelta(seconds=60))
    result=await service.query('rain',datetime.now(ZoneInfo(ZONE)).date(),'hour')
    assert result['summary']['value']==.1
    await service.stop();assert not service.cancels
    assert service.store.path.is_file()
    await hass.async_stop(force=True)


@pytest.mark.asyncio
async def test_import_api_uses_recorder_executor_and_keeps_live_cursor(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone=ZONE;hass.config.components.add('recorder')
    cfg=deepcopy(DEFAULT_CONFIG);cfg['entities']={'rain_total':'sensor.rain'}
    service=ArchiveService(hass,{'config':cfg});await hass.async_add_executor_job(service.store.initialize)
    day=date(2026,10,10);start,end=boundaries(day,ZONE)
    data={'sensor.rain':[state(2,start),state(2.5,start+3600)]}
    recorder=SimpleNamespace(async_add_executor_job=AsyncMock(return_value=(data, [(start, end)])))
    with patch('homeassistant.components.recorder.get_instance',return_value=recorder):
        await service.import_day(day)
        await service.import_day(day)
    assert recorder.async_add_executor_job.await_count==1
    assert rows(service.store,Source('rain','sensor.rain','counter'),start,end)[0][5]==.5
    hass.config.components.remove('recorder');await hass.async_stop(force=True)


@pytest.mark.asyncio
async def test_import_does_not_bridge_home_assistant_outage(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone=ZONE;hass.config.components.add('recorder')
    cfg=deepcopy(DEFAULT_CONFIG);cfg['entities']={'rain_total':'sensor.rain'}
    service=ArchiveService(hass,{'config':cfg});await hass.async_add_executor_job(service.store.initialize)
    day=date(2026,10,10);start,end=boundaries(day,ZONE)
    data={'sensor.rain':[state(10,start),state(10.1,start+1800),state(11,start+7200),state(11.2,start+9000)]}
    recorder=SimpleNamespace(async_add_executor_job=AsyncMock(return_value=(data,[(start,start+3600),(start+7200,end)])))
    with patch('homeassistant.components.recorder.get_instance',return_value=recorder):
        await service.import_day(day)
    result=await service.query('rain',day,'hour')
    assert result['summary']['value']==.3
    assert result['summary']['partial']
    assert result['points'][1]['value'] is None
    hass.config.components.remove('recorder');await hass.async_stop(force=True)


def test_recorder_run_windows_use_real_sqlalchemy_schema():
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from homeassistant.components.recorder.db_schema import RecorderRuns
    from custom_components.station_meteo.archive import recorder_day
    engine=create_engine('sqlite:///:memory:');RecorderRuns.__table__.create(engine)
    start=stamp('2026-10-10T00:00:00+02:00');end=start+86400
    with Session(engine) as session:
        session.add(RecorderRuns(start=datetime.fromtimestamp(start,UTC),end=datetime.fromtimestamp(start+3600,UTC)))
        session.add(RecorderRuns(start=datetime.fromtimestamp(start+7200,UTC),end=None));session.commit()
    @contextmanager
    def scoped(**kwargs):
        with Session(engine) as session:yield session
    with patch('homeassistant.components.recorder.history.get_significant_states',return_value={}),patch('homeassistant.components.recorder.util.session_scope',scoped):
        data,windows=recorder_day(None,start,end,['sensor.rain'])
    assert data=={} and windows==[(start,start+3600),(start+7200,end)]


@pytest.mark.asyncio
async def test_source_change_imports_today_and_cancels_collection_cleanly(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone=ZONE
    cfg=deepcopy(DEFAULT_CONFIG);cfg['entities']={'rain_total':'sensor.first'}
    service=ArchiveService(hass,{'config':cfg});await service.start()
    hass.states.async_set('sensor.first','0',{'unit_of_measurement':'mm'})
    await hass.async_block_till_done()
    cfg['entities']['rain_total']='sensor.second'
    with patch.object(service,'import_day',AsyncMock()) as importer:
        await service.reconfigure()
        importer.assert_awaited_once()
    assert any(source.entity=='sensor.second' for source,_,_ in service.queue)
    await service.stop();await hass.async_stop(force=True)
