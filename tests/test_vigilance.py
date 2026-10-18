from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch
from homeassistant.core import State
from custom_components.station_meteo.vigilance import alert_snapshot,current_alerts


def test_colors_freshness_and_unchanged_green_report():
    now=datetime.now(timezone.utc)
    state=State('sensor.66_weather_alert','Orange',{'Orages':'Jaune','Pluie-inondation':'Orange','friendly_name':'66 Weather alert'},last_updated=now-timedelta(days=3),last_reported=now)
    data=alert_snapshot(state,'66',now)
    assert data['status']=='available' and data['level']==3
    assert {p['name'] for p in data['phenomena']}=={'Orages','Pluie-inondation'}
    assert data['source'].endswith('pyrenees-orientales')
    assert alert_snapshot(state,'66',now+timedelta(hours=1))['status']=='stale'
    state=State('sensor.66_weather_alert','Vert',{},last_updated=now-timedelta(days=3),last_reported=now)
    assert alert_snapshot(state,now=now)['status']=='available'
    assert alert_snapshot(State('sensor.x','unavailable',{}),now=now)['status']=='unavailable'
    assert alert_snapshot(State('sensor.x','anything',{}),now=now)['level']==0


def test_auto_department_selection_manual_override_and_last_good():
    def entry(eid,uid,cfg='mf'):
        return SimpleNamespace(entity_id=eid,unique_id=uid,platform='meteo_france',domain=eid.split('.')[0],disabled_by=None,config_entry_id=cfg)
    entries={'sensor.66_weather_alert':entry('sensor.66_weather_alert','66 Weather alert'), 'weather.station':entry('weather.station','weather','mf')}
    states={'sensor.66_weather_alert':State('sensor.66_weather_alert','Orange',{'Pluie-inondation':'Orange'})}
    hass=SimpleNamespace(states=SimpleNamespace(get=states.get));runtime={'config':{'entities':{'weather':'weather.station'}}}
    registry=SimpleNamespace(entities=entries,async_get=entries.get)
    with patch('custom_components.station_meteo.vigilance.er.async_get',return_value=registry):
        data=current_alerts(hass,runtime);assert data['department']=='66' and data['level']==3
        states['sensor.66_weather_alert']=State('sensor.66_weather_alert','unavailable',{})
        data=current_alerts(hass,runtime);assert data['status']=='unavailable' and data['level']==3 and data['phenomena']
        entries['sensor.75_weather_alert']=entry('sensor.75_weather_alert','75 Weather alert','paris')
        runtime['config']['entities']={}
        assert current_alerts(hass,runtime)['status']=='choose'
        runtime['config']['entities']['weather_alert']='sensor.66_weather_alert'
        assert current_alerts(hass,runtime)['entity_id']=='sensor.66_weather_alert'
        runtime['config']['entities']['weather_alert']='sensor.missing'
        assert current_alerts(hass,runtime)['status']=='unavailable'
