"""Exercise actual Home Assistant service calls and alert transitions."""
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from homeassistant.core import HomeAssistant
from custom_components.station_meteo.notifications import NotificationManager, pressure_delta
from custom_components.station_meteo.const import DEFAULT_CONFIG, DEFAULT_NOTIFICATIONS
from custom_components.station_meteo.websocket import validate_config


def test_pressure_window_and_outages():
    samples=[(i*60,1000-i/60) for i in range(181)]
    assert pressure_delta(samples,10800)==-3
    assert pressure_delta(samples[1:],10800)==pytest.approx(-179/60)
    assert pressure_delta(samples[4:],10800) is None
    assert pressure_delta(samples[:50]+samples[80:],10800) is None
    assert pressure_delta(samples,12000) is None


@pytest.mark.asyncio
async def test_alerts_edges_cooldown_units_and_disable(tmp_path):
    hass=HomeAssistant(str(tmp_path))
    sent=[]
    async def notify(call):sent.append(dict(call.data))
    hass.services.async_register('notify','mobile_app_test',notify)
    cfg={**DEFAULT_CONFIG,'language':'fr','entities':{'pressure':'sensor.pressure','wind_gust':'sensor.gust','rain_status':'binary_sensor.rain','weather':'weather.test'},'notifications':{**DEFAULT_NOTIFICATIONS,'enabled':True,'recipients':['notify.mobile_app_test'],'gust':True,'gust_threshold':60}}
    runtime={'config':cfg}
    manager=NotificationManager(hass,runtime)
    try:
        hass.states.async_set('sensor.pressure','100000',{'unit_of_measurement':'Pa'})
        hass.states.async_set('sensor.gust','20',{'unit_of_measurement':'m/s'})
        hass.states.async_set('binary_sensor.rain','on')
        hass.states.async_set('weather.test','lightning',{'supported_features':0})
        assert manager.value('pressure')==1000
        assert manager.value('wind_gust')==72
        await manager._check(20000)
        assert len(sent)==3  # pressure needs full window, rain/gust/storm fire
        assert any('72.0 km/h' in x['message'] for x in sent)
        await manager._check(20060)
        assert len(sent)==3  # continued condition sends no duplicates
        hass.states.async_set('binary_sensor.rain','off')
        await manager._check(20120)
        hass.states.async_set('binary_sensor.rain','on')
        await manager._check(20180)
        assert len(sent)==3  # re-trigger waits for cooldown
        await manager._check(23660)
        assert len(sent)==4
        cfg['notifications']['enabled']=False
        hass.states.async_set('sensor.gust','100')
        await manager._check(28000)
        assert len(sent)==4
        cfg['notifications']['enabled']=True
        cfg['notifications']['rain']=False
        cfg['notifications']['gust']=False
        cfg['notifications']['storm']=False
        manager.pressure_entity='sensor.pressure'
        manager.samples.extend((30000+i*60,1000-i/60) for i in range(180))
        hass.states.async_set('sensor.pressure','99700',{'unit_of_measurement':'Pa'})
        await manager._check(40800)
        assert len(sent)==5
        assert '−3.0 hPa' in sent[-1]['message']
        manager.stop()
    finally:
        await hass.async_stop(force=True)


@pytest.mark.asyncio
async def test_forecast_storm_and_target_validation(tmp_path):
    from homeassistant.core import SupportsResponse
    from homeassistant.helpers import entity_registry as er, device_registry as dr
    hass=HomeAssistant(str(tmp_path))
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    sent=[]
    async def notify(call):sent.append(dict(call.data))
    async def forecasts(call):return {'weather.test':{'forecast':[{'datetime':datetime.fromtimestamp(22000,timezone.utc).isoformat(),'condition':'lightning-rainy'}]}}
    hass.services.async_register('notify','mobile_app_test',notify)
    hass.services.async_register('weather','get_forecasts',forecasts,supports_response=SupportsResponse.ONLY)
    cfg={**DEFAULT_CONFIG,'language':'fr','entities':{'weather':'weather.test'},'notifications':{**DEFAULT_NOTIFICATIONS,'enabled':True,'recipients':['notify.mobile_app_test']}}
    manager=NotificationManager(hass,{'config':cfg})
    try:
        hass.states.async_set('weather.test','partlycloudy',{'supported_features':2})
        assert validate_config(hass,cfg)['notifications']['enabled']
        assert validate_config(hass,cfg)['theme'] == 'light'
        assert validate_config(hass,{**cfg,'theme':'schedule','theme_dark_start':'20:00','theme_dark_end':'08:00'})['theme']=='schedule'
        assert validate_config(hass,{**cfg,'notifications':{**cfg['notifications'],'vigilance':True}})['notifications']['vigilance']
        for invalid in ({'theme':'night'}, {'theme_dark_start':'25:00'}, {'theme_dark_end':'8:00'}, {'theme_dark_start':True}, {'theme':'schedule','theme_dark_start':'08:00','theme_dark_end':'08:00'}):
            with pytest.raises(ValueError):validate_config(hass,{**cfg,**invalid})
        for opts in ({'enabled':'yes'},{'cooldown':0},{'gust_threshold':float('nan')},{'recipients':['notify.nonexistent']},{'extra':True}):
            with pytest.raises(ValueError):validate_config(hass,{**cfg,'notifications':{**DEFAULT_NOTIFICATIONS,**opts}})
        await manager._check(20000)
        assert len(sent)==1
        assert 'orage' in sent[0]['message'].lower()
        await manager._check(20100)
        assert len(sent)==1
        hass.states.async_set('weather.test','unavailable')
        await manager._check(24000)
        assert len(sent)==1
    finally:
        await hass.async_stop(force=True)
