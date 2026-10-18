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
        assert len(validate_config(hass, cfg)['map_buttons']) == 11
        cfg['map_buttons'].append(deepcopy(custom[0]))
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'].pop()
        cfg['map_buttons'][-1]['id'] = 'custom1'
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'][-1]['id'] = 'custom5'
        cfg['map_buttons'][-1]['url'] = 'javascript:alert(1)'
        with pytest.raises(ValueError): validate_config(hass, cfg)
        cfg['map_buttons'].pop(7)
        cfg['map_buttons'][-1]['url'] = 'https://example.org/map'
        assert len(validate_config(hass, cfg)['map_buttons']) == 10
