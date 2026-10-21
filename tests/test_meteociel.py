"""Native map geometry, declared times and trusted source validation."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from custom_components.station_meteo.meteociel import viewport, tile_plan, radar_metadata, projected_points, async_meteociel
from custom_components.station_meteo.const import DEFAULT_MAP_BUTTONS, DEFAULT_CONFIG, normalize_map_buttons
from custom_components.station_meteo.websocket import validate_config


@pytest.mark.asyncio
async def test_animated_radar_layers_and_city_controls():
    runtime = {'config': deepcopy(DEFAULT_CONFIG)}
    html = 'radardate2[0]="202610190650";radardate2[1]="202610190655";'
    reader = AsyncMock(return_value=html)
    labels = AsyncMock(return_value=[])
    with patch('custom_components.station_meteo.meteociel.read_source', reader), patch('custom_components.station_meteo.meteociel.city_labels', labels), patch('custom_components.station_meteo.meteociel.async_get_clientsession', return_value=None):
        result = await async_meteociel(None, runtime, 6, {'cities': 2, 'roads': True, 'rivers': False, 'relief': True})
        assert result['kind'] == 'radar' and len(result['frames']) == 2
        assert all('/101_' in tile['url'] for tile in result['backgrounds'])
        assert labels.await_args.args[2] == 2
        assert result['frames'][0]['time'] < result['frames'][1]['time']
        assert all(frame['tiles'] for frame in result['frames'])
        plain = await async_meteociel(None, runtime, 6, {'cities': 0, 'roads': False, 'rivers': False, 'relief': False})
        assert plain['backgrounds'] == [] and len(plain['frames']) == 2
        assert reader.await_count == 1  # Layer changes reuse recent metadata.
        moved = await async_meteociel(None, runtime, 6, {'cities': 0}, {'x': 5000, 'y': 8000, 'zoom': 2})
        assert moved['viewport']['x'] == 5000 and moved['viewport']['zoom'] == 2
        assert moved['frames'][0]['tiles'] != result['frames'][0]['tiles']
        assert reader.await_count == 1


def test_navigation_rejects_bad_coordinates_and_clamps_edges():
    url = DEFAULT_MAP_BUTTONS[0]['url']
    for value in ({'x': 0, 'y': 0}, {'x': 0, 'y': 0, 'zoom': 7}, {'x': -1, 'y': 0, 'zoom': 3}, {'x': float('nan'), 'y': 0, 'zoom': 3}, {'x': True, 'y': 0, 'zoom': 3}, {'x': 0, 'y': 0, 'zoom': 3, 'host': 'localhost'}):
        with pytest.raises(ValueError): viewport(url, value)
    for maximum, index in ((6, 0), (4, 6)):
        for zoom in range(maximum+1):
            for edge in (0, 768*2**maximum):
                view = viewport(DEFAULT_MAP_BUTTONS[index]['url'], {'x': edge, 'y': edge, 'zoom': zoom})
                assert view['left'] >= 0 and view['top'] >= 0
                assert view['left'] + 768/view['scale'] <= 768*2**maximum
                assert 1 <= len(tile_plan(view)) <= 9


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
        radar=viewport(DEFAULT_MAP_BUTTONS[6]['url'], {'x': 6637.38, 'y': 10025.69, 'zoom': zoom})
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
    assert len(upgraded)==len(DEFAULT_MAP_BUTTONS)
    assert upgraded[2]['mode']=='meteociel' and 'animation-visible-composition-mtg' in upgraded[2]['url']
    assert [c['id'] for c in upgraded[3:]]==['humidity','rain24','gusts','precipitation','cumuls']
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
        result = await async_meteociel(None, runtime, len(DEFAULT_MAP_BUTTONS))
    assert result['animated'] and result['image_only'] and result['embedded_time']
    assert result['frames'][0]['url'].startswith('https://www.meteociel.fr/cartes_obs/radar/lastradar5m_so.gif?station_meteo_refresh=')
    assert result['source'] == card['url']
    assert await async_meteociel(None, runtime, 10) == {'frames': [], 'error': 'disabled'}


def test_lightning_options_and_duration_filter():
    from custom_components.station_meteo.meteociel import lightning_options
    assert lightning_options()=={'duration':30,'cities':1,'roads':False,'rivers':True,'relief':False}
    for minutes in (2,5,10,30,60,120):
        assert lightning_options({'duration':minutes})['duration']==minutes
    for invalid in ({'duration':3},{'cities':4},{'roads':1},{'duration':True},{'host':'https://example.org'}):
        with pytest.raises(ValueError):lightning_options(invalid)
    view=viewport(DEFAULT_MAP_BUTTONS[0]['url'])
    p={'x':(view['left']+100/view['scale'])/64,'y':(view['top']+200/view['scale'])/64,'d':3600,'_id':'batch:4'}
    assert projected_points([p],view,minutes=30)==[]
    assert projected_points([p],view,minutes=120)[0]['id']=='batch:4'


@pytest.mark.asyncio
async def test_lightning_incremental_cache_ids_expiry_and_no_data():
    from custom_components.station_meteo.meteociel import lightning_snapshot
    from datetime import timedelta
    now=datetime(2026,10,19,7,0,tzinfo=timezone.utc)
    reader=AsyncMock(side_effect=['{"last":"100","items":[{"x":1,"y":2,"d":110}]}','{"last":"101","items":[{"x":3,"y":4,"d":1}]}','NO'])
    with patch('custom_components.station_meteo.meteociel.read_source',reader):
        first=await lightning_snapshot(None,None,now,2)
        assert first['items'][0]['_id']=='100:0'
        second=await lightning_snapshot(None,{'at':now,'content':first},now+timedelta(seconds=5),2)
        assert [p['_id'] for p in second['items']]==['100:0','101:0']
        third=await lightning_snapshot(None,{'at':now+timedelta(seconds=5),'content':second},now+timedelta(seconds=15),2)
        assert [p['_id'] for p in third['items']]==['101:0']
        assert third['items'][0]['d']==11
        assert reader.call_args_list[0].args[2]['duree']==2
        assert reader.call_args_list[1].args[2]['last']=='100'
        assert 'first' not in reader.call_args_list[1].args[2]


@pytest.mark.asyncio
async def test_lightning_layers_cities_and_cache_separation():
    from custom_components.station_meteo.meteociel import city_labels
    runtime={'config':deepcopy(DEFAULT_CONFIG)}
    reader=AsyncMock(return_value='{"last":"123","items":[]}')
    labels=AsyncMock(return_value=[])
    with patch('custom_components.station_meteo.meteociel.async_get_clientsession',return_value=None),patch('custom_components.station_meteo.meteociel.read_source',reader),patch('custom_components.station_meteo.meteociel.city_labels',labels):
        first=await async_meteociel(None,runtime,0,{'duration':120,'cities':3,'roads':True,'rivers':False,'relief':True})
        assert first['duration']==120 and '120 min' in first['credit']
        assert '/101_' in first['backgrounds'][0]['url']
        assert labels.call_args.args[2]==3
        second=await async_meteociel(None,runtime,0,{'duration':120,'cities':0})
        assert reader.await_count==1
        assert '/010_' in second['backgrounds'][0]['url']
        await async_meteociel(None,runtime,0,{'duration':2})
        assert reader.await_count==2 # durations cannot share their observation cache
    view=viewport(DEFAULT_MAP_BUTTONS[0]['url'])
    city={'x':(view['left']+100/view['scale'])/64,'y':(view['top']+100/view['scale'])/64,'n':'Test'}
    reader=AsyncMock(return_value=__import__('json').dumps([city]))
    with patch('custom_components.station_meteo.meteociel.read_source',reader):
        assert await city_labels(None,view,0)==[]
        reader.assert_not_awaited()
        for level,limit in [(1,20000),(2,5000),(3,0)]:
            assert (await city_labels(None,view,level))[0]['name']=='Test'
            assert reader.call_args.args[2]['limit']==limit


@pytest.mark.asyncio
async def test_lightning_explicit_no_data_is_an_empty_snapshot_not_a_failure():
    from custom_components.station_meteo.meteociel import lightning_snapshot
    now=datetime(2026,10,19,7,0,tzinfo=timezone.utc)
    reader=AsyncMock(return_value='NO')
    with patch('custom_components.station_meteo.meteociel.read_source',reader):
        result=await lightning_snapshot(None,None,now,30)
        assert result['items']==[] and result['last']=='0'
        await lightning_snapshot(None,{'at':now,'content':result},now,30)
        assert reader.call_args.args[2]['first']==1


@pytest.mark.asyncio
async def test_lightning_expired_cursor_resynchronizes_selected_window_once():
    from custom_components.station_meteo.meteociel import lightning_snapshot
    now=datetime(2026,10,19,7,0,tzinfo=timezone.utc)
    cached={'at':now,'content':{'last':'100','items':[{'x':1,'y':2,'d':10,'_id':'old:0'}]}}
    reader=AsyncMock(side_effect=['ERR','{"last":"150","items":[{"x":3,"y":4,"d":1}]}'])
    with patch('custom_components.station_meteo.meteociel.read_source',reader):
        result=await lightning_snapshot(None,cached,now,5)
    assert result['reset'] and result['last']=='150'
    assert len(result['items'])==1 and result['items'][0]['_id']=='150:0'
    assert reader.call_args_list[0].args[2]['last']=='100'
    assert reader.call_args_list[1].args[2]['duree']==5


@pytest.mark.asyncio
async def test_lightning_initial_source_error_remains_visible_and_not_empty_weather():
    from custom_components.station_meteo.meteociel import lightning_snapshot
    reader=AsyncMock(return_value='ERR')
    with patch('custom_components.station_meteo.meteociel.read_source',reader):
        with pytest.raises(ValueError):
            await lightning_snapshot(None,None,datetime.now(timezone.utc),5)
    assert reader.await_count==1
