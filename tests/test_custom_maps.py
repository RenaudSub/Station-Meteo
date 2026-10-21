from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from custom_components.station_meteo.const import DEFAULT_CONFIG, DEFAULT_MAP_BUTTONS, normalize_map_buttons
from custom_components.station_meteo.websocket import validate_config


def test_custom_maps_persist_and_validate():
    cfg = deepcopy(DEFAULT_CONFIG)
    custom = [{**DEFAULT_MAP_BUTTONS[0], 'id': f'custom{i}', 'name': f'Carte {i}', 'mode': 'iframe', 'url': 'https://example.org/map'} for i in range(1, 6)]
    custom[0].update(name='Précipitations', mode='meteociel', url='https://www.meteociel.fr/observations-meteo/radar2.php?region=so')
    cfg['map_buttons'].extend(custom)
    assert normalize_map_buttons(cfg['map_buttons']) == cfg['map_buttons']
    hass = SimpleNamespace(services=SimpleNamespace(async_services=lambda: {}), config=SimpleNamespace(latitude=42.5, longitude=2.5))
    with patch('custom_components.station_meteo.websocket.er.async_get', return_value=SimpleNamespace(entities={})):
        assert len(validate_config(hass, cfg)['map_buttons']) == len(DEFAULT_MAP_BUTTONS) + 5
        cfg['map_buttons'].append(deepcopy(custom[0]))
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'].pop()
        cfg['map_buttons'][-1]['id'] = 'custom1'
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'][-1]['id'] = 'custom5'
        cfg['map_buttons'][-1]['url'] = 'javascript:alert(1)'
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'].pop(len(DEFAULT_MAP_BUTTONS) + 1)
        cfg['map_buttons'][-1]['url'] = 'https://example.org/map'
        assert len(validate_config(hass, cfg)['map_buttons']) == len(DEFAULT_MAP_BUTTONS) + 4


def test_new_radar_button_preserves_all_existing_custom_maps():
    old = deepcopy(DEFAULT_MAP_BUTTONS[:6])
    old[1].update(name='Mon radar', enabled=False, url='https://example.org/radar', mode='tab')
    custom = [{**old[0], 'id': f'custom{i}', 'name': f'Ma carte {i}', 'url': f'https://example.org/{i}', 'mode': 'iframe'} for i in range(1, 6)]
    upgraded = normalize_map_buttons(old + custom)
    assert upgraded[:6] == old
    assert upgraded[6] == DEFAULT_MAP_BUTTONS[6]
    assert upgraded[len(DEFAULT_MAP_BUTTONS):] == custom
    assert normalize_map_buttons(upgraded) == upgraded


def test_rain_snow_radar_updates_only_the_previous_default():
    old = deepcopy(DEFAULT_MAP_BUTTONS)
    old[1]['url'] = 'https://www.meteociel.fr/observations-meteo/radarzoom.php?x=6742.28&y=9941.72&ech=11&zoom=4'
    assert normalize_map_buttons(old)[1]['url'] == DEFAULT_MAP_BUTTONS[1]['url']
    old[1].update(url='https://www.meteociel.fr/observations-meteo/radar2.php?region=ne&mode=1', name='Mon radar', enabled=False)
    assert normalize_map_buttons(old)[1] == old[1]
