"""Live satellite cadence parsing and configurable map validation."""
from datetime import datetime, timezone
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import pytest
from custom_components.station_meteo.satellite import recent_times, image_urls
from custom_components.station_meteo.const import DEFAULT_CONFIG
from custom_components.station_meteo.websocket import validate_config


def metadata(dimension):
    return f'<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability><Layer><Layer><Name>mtg_fd:rgb_geocolour</Name><Dimension name="time">{dimension}</Dimension></Layer></Layer></Capability></WMS_Capabilities>'


def test_recent_frames_use_declared_cadence_and_never_future():
    now=datetime(2026,10,11,11,36,tzinfo=timezone.utc)
    times=recent_times(metadata('2026-10-10T00:00:00Z/2026-10-11T12:00:00Z/PT10M'),now)
    assert len(times)==12 and times[-1]=='2026-10-11T11:30:00Z'
    assert times[0]=='2026-10-11T09:40:00Z'
    explicit=recent_times(metadata('2026-10-11T11:00:00Z,2026-10-11T11:10:00Z,2026-10-11T12:00:00Z'),now)
    assert len(explicit)==2
    with pytest.raises(ValueError):recent_times(metadata('bad'),now)


def test_satellite_url_crops_without_changing_source():
    frames=image_urls(['2026-10-11T11:30:00Z'],42.627506,2.593331,4)
    url=urlsplit(frames[0]['url']);args=parse_qs(url.query)
    assert url.hostname=='view.eumetsat.int'
    assert args['LAYERS']==['mtg_fd:rgb_geocolour']
    assert args['TIME']==['2026-10-11T11:30:00Z']
    west,south,east,north=map(float,args['BBOX'][0].split(','))
    assert west<2.593331<east and south<42.627506<north
    with pytest.raises(ValueError):image_urls(['2026-10-11T11:30:00Z'],89,170,8)


def test_map_configuration_round_trip_visibility_and_invalid_targets():
    hass=SimpleNamespace(services=SimpleNamespace(async_services=lambda:{}),states=SimpleNamespace(get=lambda _:None))
    cfg=deepcopy(DEFAULT_CONFIG)
    cfg['map_buttons'][0].update(name='Ma carte',enabled=False,mode='tab',url='https://example.org/weather')
    with patch('custom_components.station_meteo.websocket.er.async_get',return_value=SimpleNamespace(async_get=lambda _:None)):
        result=validate_config(hass,cfg)
        assert result['map_buttons'][0]['name']=='Ma carte' and not result['map_buttons'][0]['enabled']
        for invalid in ['javascript:alert(1)','http://example.org','https://user:password@example.org','//example.org']:
            cfg['map_buttons'][0]['url']=invalid
            with pytest.raises(ValueError):validate_config(hass,cfg)
        cfg['map_buttons'][0]['url']='https://example.org'
        cfg['map_buttons'][2]['zoom']=float('nan')
        with pytest.raises(ValueError):validate_config(hass,cfg)
