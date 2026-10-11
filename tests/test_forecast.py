"""Forecast fallback aligns slots, preserves zero and normalizes provider units."""
from datetime import datetime, timezone
import pytest
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from custom_components.station_meteo.forecast import normalize, merge_rows, async_forecasts
from custom_components.station_meteo.notifications import NotificationManager
from custom_components.station_meteo.const import DEFAULT_CONFIG, DEFAULT_NOTIFICATIONS

NOW=datetime(2026,10,10,18,tzinfo=timezone.utc).timestamp()
def row(hour,**values):return {'datetime':f'2026-10-10T{hour:02}:00:00+00:00',**values}


def test_same_hour_missing_fields_zero_and_source_units():
    p=normalize([row(18,temperature=0,precipitation=0,condition='cloudy'),row(19,temperature=None,condition='unknown'),row(17,temperature=5)],{},'weather.primary')
    b=normalize([row(18,temperature=68,precipitation=1,precipitation_probability=0,wind_speed=10),row(19,temperature=50,precipitation_probability=20),row(20,temperature=32)],{'temperature_unit':'°F','wind_speed_unit':'mph','precipitation_unit':'in'},'weather.backup')
    merged=merge_rows(p,b,'hourly',NOW,'Europe/Paris')
    assert len(merged)==3
    assert merged[0]['temperature']==0 and merged[0]['precipitation']==0
    assert merged[0]['precipitation_probability']==0
    assert merged[0]['wind_speed']==pytest.approx(16.09344)
    assert merged[0]['_sources']['temperature']=='weather.primary'
    assert merged[0]['_sources']['precipitation_probability']=='weather.backup'
    assert merged[1]['temperature']==10
    assert merged[2]['temperature']==0
    wrong=merge_rows(p[:1],b[1:],'hourly',NOW,'Europe/Paris')
    assert 'precipitation_probability' not in wrong[0]
    assert p[0]['temperature']==0 and 'wind_speed' not in p[0]  # no input mutation


def test_daily_local_date_match_and_invalid_values():
    p=normalize([{'datetime':'2026-10-10T22:00:00+00:00','temperature':20,'precipitation':0,'humidity':float('nan')}],{},'weather.primary')
    b=normalize([{'datetime':'2026-10-11T06:00:00+00:00','temperature':30,'templow':10,'precipitation_probability':-1},{'datetime':'2026-10-12T06:00:00+00:00','temperature':25}],{},'weather.backup')
    merged=merge_rows(p,b,'daily',NOW,'Europe/Paris')
    assert merged[0]['temperature']==20 and merged[0]['templow']==10
    assert merged[0]['precipitation']==0
    assert 'humidity' not in merged[0] and 'precipitation_probability' not in merged[0]
    assert len(merged)==2


@pytest.mark.asyncio
async def test_primary_failure_unavailability_return_and_storm_alert(tmp_path):
    hass=HomeAssistant(str(tmp_path));hass.config.time_zone='Europe/Paris'
    fail=True;sent=[]
    async def forecasts(call):
        eid=call.data['entity_id']
        if eid=='weather.primary' and fail:raise HomeAssistantError('primary offline')
        return {eid:{'forecast':[row(19,temperature=10,condition='cloudy' if eid=='weather.primary' else 'lightning-rainy',precipitation_probability=0 if eid=='weather.backup' else None)]}}
    async def notify(call):sent.append(call.data)
    hass.services.async_register('weather','get_forecasts',forecasts,supports_response=SupportsResponse.ONLY)
    hass.services.async_register('notify','mobile_app_test',notify)
    cfg={**DEFAULT_CONFIG,'language':'fr','entities':{'weather':'weather.primary','weather_fallback':'weather.backup'},'notifications':{**DEFAULT_NOTIFICATIONS,'enabled':True,'recipients':['notify.mobile_app_test']}}
    try:
        for eid in cfg['entities'].values():hass.states.async_set(eid,'cloudy',{'supported_features':3,'friendly_name':eid})
        result=await async_forecasts(hass,cfg,now=NOW)
        assert result['hourly'][0]['_sources']['condition']=='weather.backup'
        assert result['errors']==['weather.primary']
        manager=NotificationManager(hass,{'config':cfg})
        await manager._check(NOW)
        assert len(sent)==1 and 'orage' in sent[0]['message'].lower()
        fail=False
        result=await async_forecasts(hass,cfg,now=NOW)
        assert result['hourly'][0]['condition']=='cloudy'
        assert result['hourly'][0]['_sources']['precipitation_probability']=='weather.backup'
        hass.states.async_set('weather.primary','unavailable')
        result=await async_forecasts(hass,cfg,now=NOW)
        assert result['hourly'][0]['condition']=='lightning-rainy'
        hass.states.async_set('weather.backup','unavailable')
        result=await async_forecasts(hass,cfg,now=NOW)
        assert result['hourly']==[] and result['daily']==[]
    finally:await hass.async_stop(force=True)
