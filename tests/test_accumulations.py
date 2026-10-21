"""Accumulation products keep their own tiles, palettes, and forecast times."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from custom_components.station_meteo.const import DEFAULT_CONFIG, DEFAULT_MAP_BUTTONS, normalize_map_buttons
from custom_components.station_meteo.meteociel import ACCUMULATIONS, accumulation_metadata, async_meteociel, viewport


def html(product):
    return f'''var piafFirstEch = 2;
radardate[0]="2026/10/19";radardate2[0]="202610190650";
radardate[1]="2026/10/19";radardate2[1]="202610190655";
radardate[2]="15";radardate2[2]="0700";
radardate[3]="15";radardate2[3]="0705";
keyColors[0]="#85FAFB";keyValues[0]={product};'''


@pytest.mark.asyncio
async def test_eight_products_use_separate_metadata_and_correct_tiles():
    runtime = {'config': deepcopy(DEFAULT_CONFIG)}
    reader = AsyncMock(side_effect=lambda session, url, params: html(params['lame']))
    with patch('custom_components.station_meteo.meteociel.async_get_clientsession', return_value=None), patch('custom_components.station_meteo.meteociel.read_source', reader):
        for product, prefix in ACCUMULATIONS.items():
            result = await async_meteociel(None, runtime, 7, {'cities': 0}, None, product)
            assert result['product'] == product and result['unit'] == 'mm'
            assert result['palette'][0]['value'] == product
            assert f'/tileslame/2026/10/19/4/{prefix}202610190650-' in result['frames'][0]['tiles'][0]['url']
            assert len(result['frames']) == (4 if product == 15 else 2)
            if product == 15:
                assert '/tilespiaf/15/4/0700-' in result['frames'][2]['tiles'][0]['url']
                assert result['frames'][2]['forecast']
                assert result['frames'][2]['time'].endswith('07:00:00+00:00')
        assert reader.await_count == 8
        await async_meteociel(None, runtime, 7, {'cities': 0}, None, 1)
        assert reader.await_count == 8
        invalid = await async_meteociel(None, runtime, 7, {'cities': 0}, None, 99)
        assert invalid['error'] == 'unavailable'


def test_forecast_midnight_rollover_and_untrusted_paths():
    source = html(15).replace('202610190650', '202610192350').replace('202610190655', '202610192355').replace('0700', '0000').replace('0705', '0005')
    result = accumulation_metadata(source, 15, datetime(2026, 10, 19, 23, 59, tzinfo=timezone.utc))
    assert result['frame_specs'][2]['time'] == '2026-10-20T00:00:00+00:00'
    bad = source.replace('radardate[2]="15"', 'radardate[2]="../outside"')
    assert len(accumulation_metadata(bad, 15, datetime(2026, 10, 19, 23, 59, tzinfo=timezone.utc))['frame_specs']) == 3


def test_cumuls_default_migration_preserves_five_custom_buttons():
    old = deepcopy(DEFAULT_MAP_BUTTONS[:7])
    custom = [{**old[0], 'id': f'custom{i}', 'name': f'Carte {i}'} for i in range(1, 6)]
    upgraded = normalize_map_buttons(old+custom)
    assert upgraded[:7] == old and upgraded[7]['id'] == 'cumuls'
    assert upgraded[8:] == custom
    for product in ACCUMULATIONS:
        url = DEFAULT_MAP_BUTTONS[7]['url'].replace('lame=1', f'lame={product}')
        assert viewport(url)['product'] == product
    for suffix in ('lame=8', 'lame=', 'lame=1&lame=2', 'lame=1&snow=1', 'lame=1&archive=1'):
        with pytest.raises(ValueError): viewport(DEFAULT_MAP_BUTTONS[7]['url'].split('&lame=')[0]+'&'+suffix)
