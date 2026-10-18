"""Native map geometry, declared times and trusted source validation."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from custom_components.station_meteo.meteociel import viewport, tile_plan, radar_metadata, projected_points, async_meteociel
from custom_components.station_meteo.const import DEFAULT_MAP_BUTTONS, DEFAULT_CONFIG, normalize_map_buttons
from custom_components.station_meteo.websocket import validate_config


def test_fractional_viewport_matches_original_and_tiles_cover_it():
    view = viewport(DEFAULT_MAP_BUTTONS[0]['url'])
    assert view['scale'] == pytest.approx(2 ** -.1)
    assert view['left'] == pytest.approx(21246.45 - 384)
    tiles = tile_plan(view)
    assert 1 <= len(tiles) <= 9
    assert min(t['rect'][0] for t in tiles) <= 0
    assert max(t['rect'][0]+t['rect'][2] for t in tiles) >= 768
    assert min(t['rect'][1] for t in tiles) <= 0
    assert max(t['rect'][1]+t['rect'][3] for t in tiles) >= 768
    assert all(t['level']==6 for t in tiles)
    for zoom in range(5):
        radar=viewport(DEFAULT_MAP_BUTTONS[1]['url'].replace('zoom=4',f'zoom={zoom}'))
        assert len(tile_plan(radar))<=9
    for url in ['https://localhost/observations-meteo/radarzoom.php', 'https://www.meteociel.fr:8443/observations-meteo/radarzoom.php', DEFAULT_MAP_BUTTONS[1]['url']+'&snow=1', DEFAULT_MAP_BUTTONS[1]['url'].replace('zoom=4','zoom=nan')]:
        with pytest.raises(ValueError):viewport(url)


def test_radar_dates_are_declared_utc_and_palette_is_parsed():
    html='radardate2[0]="202610111210";radardate2[1]="202610111215";keyColors[0]="#01A3F3";keyValues[0]=0.2;'
    data=radar_metadata(html,datetime(2026,10,11,12,12,tzinfo=timezone.utc))
    assert data['times']==['2026-10-11T12:10:00+00:00']
    assert data['palette']==[{'color':'#01A3F3','value':.2}]
    with pytest.raises(ValueError):radar_metadata('no data')


def test_lightning_coordinates_ages_and_empty_view_are_not_errors():
    view=viewport(DEFAULT_MAP_BUTTONS[0]['url'])
    point={'x':(view['left']+100/view['scale'])/64,'y':(view['top']+200/view['scale'])/64,'d':45}
    points=projected_points([point,{'x':float('nan'),'y':0,'d':0},{'x':0,'y':0,'d':1900}],view)
    assert len(points)==1 and points[0]['x']==pytest.approx(100) and points[0]['y']==pytest.approx(200)
    assert projected_points([],view)==[]


def test_defaults_migrate_without_overwriting_customization():
    cards=deepcopy(DEFAULT_MAP_BUTTONS)
    cards[0]['mode']='iframe';cards[1].update(mode='tab',url='https://example.org/my-map',name='Carte personnelle')
    upgraded=normalize_map_buttons(cards)
    assert upgraded[0]['mode']=='meteociel'
    assert upgraded[1]==cards[1]
    hass=SimpleNamespace(services=SimpleNamespace(async_services=lambda:{}),states=SimpleNamespace(get=lambda _:None))
    cfg=deepcopy(DEFAULT_CONFIG)
    with patch('custom_components.station_meteo.websocket.er.async_get',return_value=SimpleNamespace(async_get=lambda _:None)):
        assert validate_config(hass,cfg)['map_buttons'][1]['mode']=='meteociel'
        cfg['map_buttons'][0]['url']='https://example.org'
        with pytest.raises(ValueError):validate_config(hass,cfg)
        cfg['map_buttons'][0]['mode']='iframe'
        assert validate_config(hass,cfg)['map_buttons'][0]['url']=='https://example.org'


@pytest.mark.asyncio
async def test_upstream_failure_does_not_return_a_false_empty_map():
    runtime={'config':deepcopy(DEFAULT_CONFIG)}
    with patch('custom_components.station_meteo.meteociel.async_get_clientsession'),patch('custom_components.station_meteo.meteociel.read_source',new_callable=AsyncMock,side_effect=ValueError('down')):
        result=await async_meteociel(SimpleNamespace(),runtime,1)
    assert result['error']=='unavailable' and result['frames']==[]


def test_upgrade_adds_three_buttons_and_switches_only_default_satellite():
    old = deepcopy(DEFAULT_MAP_BUTTONS[:3])
    old[2].update(mode='satellite',url='https://view.eumetsat.int/')
    upgraded = normalize_map_buttons(old)
    assert len(upgraded)==6
    assert upgraded[2]['mode']=='meteociel' and 'animation-visible-composition-mtg' in upgraded[2]['url']
    assert [c['id'] for c in upgraded[3:]]==['humidity','rain24','gusts']
    old[2].update(latitude=43.2,longitude=2.8)
    upgraded=normalize_map_buttons(old)
    assert upgraded[2]['mode']=='satellite' and upgraded[2]['latitude']==43.2
    old[2].update(mode='tab',url='https://example.org/my-satellite')
    assert normalize_map_buttons(old)[2]==old[2]


def test_named_images_and_regions_are_validated_without_remote_code():
    from custom_components.station_meteo.meteociel import source_spec, map_image_url
    for index, prefix in [(3,'humi'),(4,'rr'),(5,'rafales')]:
        spec=source_spec(DEFAULT_MAP_BUTTONS[index]['url'])
        assert spec['params']['region']=='r8'
        html=f'<img src="https://example.org/ad.png"><img src="../cartes_obs/{prefix}_r8.png" id="obs_temps">'
        assert map_image_url(html,spec)==f'https://www.meteociel.fr/cartes_obs/{prefix}_r8.png'
        with pytest.raises(ValueError):map_image_url('<img id="obs_temps" src="https://example.org/humi_r8.png">',spec)
        other=source_spec(DEFAULT_MAP_BUTTONS[index]['url'].replace('region=r8','region=r9'))
        assert other['params']['region']=='r9'
    sat=source_spec(DEFAULT_MAP_BUTTONS[2]['url'])
    assert map_image_url('<img name=satimg src="//modeles20.meteociel.fr/satellite/animsatviscolmtg.gif">',sat).endswith('animsatviscolmtg.gif')
    for malicious in ['https://localhost/observations-meteo/humi.php?region=r8',DEFAULT_MAP_BUTTONS[3]['url']+'&archive=1',DEFAULT_MAP_BUTTONS[5]['url'].replace('mode=0','mode=1'),DEFAULT_MAP_BUTTONS[3]['url'].replace('region=r8','region=../../api'),DEFAULT_MAP_BUTTONS[3]['url']+'&region=r9']:
        with pytest.raises(ValueError):source_spec(malicious)
    with pytest.raises(ValueError):map_image_url('<img id=satimg src="//modeles20.meteociel.fr/satellite/../admin.php">',sat)


@pytest.mark.asyncio
async def test_image_metadata_cache_refreshes_image_url_and_keeps_embedded_time():
    from custom_components.station_meteo.meteociel import async_image_map, source_spec
    from datetime import timedelta
    runtime={};card=DEFAULT_MAP_BUTTONS[3];spec=source_spec(card['url'])
    reader=AsyncMock(return_value='<img id="obs_temps" src="../cartes_obs/humi_r8.png">')
    now=datetime(2026,10,11,13,5,tzinfo=timezone.utc)
    with patch('custom_components.station_meteo.meteociel.read_source',reader),patch('custom_components.station_meteo.meteociel.datetime') as clock:
        clock.now.return_value=now
        first=await async_image_map(None,runtime,card,spec)
        clock.now.return_value=now+timedelta(seconds=5)
        second=await async_image_map(None,runtime,card,spec)
        assert reader.await_count==1 and first['frames'][0]['url']!=second['frames'][0]['url']
        assert second['embedded_time'] and second['frames'][0]['time'] is None
        clock.now.return_value=now+timedelta(seconds=65)
        await async_image_map(None,runtime,card,spec)
        assert reader.await_count==2


def test_regional_animated_radar_sources():
    from custom_components.station_meteo.meteociel import source_spec, map_image_url
    base = 'https://www.meteociel.fr/observations-meteo/radar2.php?region=so'
    for mode, product in [('0', 'lastradar'), ('1', 'lastsnowradar')]:
        for freq, suffix in [('5', '5m'), ('15', '')]:
            spec = source_spec(base + f'&mode={mode}&freq={freq}')
            assert spec['kind'] == 'radar_animation'
            assert spec['params'] == {'region': 'so', 'mode': mode, 'freq': freq}
            path = f'/cartes_obs/radar/{product}{suffix}_so.gif'
            assert map_image_url(f'<img src="{path}" id="img">', spec) == 'https://www.meteociel.fr' + path
    spec = source_spec(base)
    assert spec['params'] == {'region': 'so', 'mode': '0', 'freq': '5'}
    for url in [base+'&freq=1', base+'&mode=2', base+'&archive=1', base+'&region=ne', base.replace('region=so','region=../../admin'), base.replace('www.meteociel.fr','example.org')]:
        with pytest.raises(ValueError): source_spec(url)
    for src in ['https://example.org/cartes_obs/radar/lastradar5m_so.gif', '/cartes_obs/radar/lastradar5m_ne.gif', '/cartes_obs/radar/lastradar_so.gif', '/cartes_obs/radar/../admin.php']:
        with pytest.raises(ValueError): map_image_url(f'<img src="{src}" id="img">', spec)


@pytest.mark.asyncio
async def test_custom_radar_native_load_and_refresh():
    from custom_components.station_meteo.meteociel import async_meteociel
    card = {**DEFAULT_MAP_BUTTONS[0], 'id': 'custom1', 'name': 'Précipitations', 'mode': 'meteociel', 'url': 'https://www.meteociel.fr/observations-meteo/radar2.php?region=so'}
    runtime = {'config': {'map_buttons': deepcopy(DEFAULT_MAP_BUTTONS) + [card]}}
    reader = AsyncMock(return_value='<img src="/cartes_obs/radar/lastradar5m_so.gif" name="img" id="img">')
    with patch('custom_components.station_meteo.meteociel.read_source', reader), patch('custom_components.station_meteo.meteociel.async_get_clientsession', return_value=None):
        result = await async_meteociel(None, runtime, 6)
    assert result['animated'] and result['image_only'] and result['embedded_time']
    assert result['frames'][0]['url'].startswith('https://www.meteociel.fr/cartes_obs/radar/lastradar5m_so.gif?station_meteo_refresh=')
    assert result['source'] == card['url']
    assert await async_meteociel(None, runtime, 10) == {'frames': [], 'error': 'disabled'}
