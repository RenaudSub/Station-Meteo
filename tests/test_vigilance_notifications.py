from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.station_meteo.const import DEFAULT_CONFIG, DEFAULT_NOTIFICATIONS
from custom_components.station_meteo.notifications import NotificationManager


def setup_manager():
    config = deepcopy(DEFAULT_CONFIG)
    config.update(language='fr', entities={})
    config['notifications'] = {**DEFAULT_NOTIFICATIONS, 'enabled': True, 'vigilance': True, 'storm': False, 'recipients': ['notify.first', 'notify.second']}
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda eid: None), services=SimpleNamespace(async_call=AsyncMock()))
    return NotificationManager(hass, {'config': config}), config, hass.services.async_call


def snapshot(level=1, phenomena=None):
    return {'entity_id': 'sensor.66_weather_alert', 'department': '66', 'status': 'available', 'level': level, 'phenomena': phenomena or [], 'source': 'https://vigilance.meteofrance.fr/fr/pyrenees-orientales'}


@pytest.mark.asyncio
async def test_all_vigilance_changes_without_duplicates_or_cooldown_suppression():
    manager, config, send = setup_manager()
    current = snapshot()
    with patch('custom_components.station_meteo.notifications.current_alerts', side_effect=lambda *args: current):
        await manager._check(1000)
        assert send.await_count == 0  # Baseline when enabled, including restart.
        current = snapshot(2, [{'name': 'Orages', 'level': 2}])
        await manager._check(1060)
        assert send.await_count == 2
        assert 'Verte → Jaune' in send.await_args.args[2]['message']
        current['received'] = 'new report, unchanged warning'
        await manager._check(1120)
        assert send.await_count == 2
        current['phenomena'].append({'name': 'Pluie-inondation', 'level': 2})
        await manager._check(1180)
        assert send.await_count == 4  # New phenomenon, same general colour.
        current['phenomena'].reverse()
        await manager._check(1240)
        assert send.await_count == 4
        for level in (3, 4):
            current = snapshot(level, [{'name': 'Pluie-inondation', 'level': level}])
            await manager._check(1240+level*60)
        assert send.await_count == 8  # Escalations do not wait the 60min cooldown.
        current = {**snapshot(), 'status': 'unavailable'}
        await manager._check(1600)
        current['status'] = 'stale'
        await manager._check(1660)
        assert send.await_count == 8
        current['status'] = 'available'
        await manager._check(1720)
        assert send.await_count == 10
        assert 'Rouge → Verte' in send.await_args.args[2]['message']
        current['entity_id'] = 'sensor.75_weather_alert'
        current['department'] = '75'
        await manager._check(1780)
        assert send.await_count == 10  # Choosing another department is a baseline.
        config['notifications']['vigilance'] = False
        await manager._check(1840)
        config['notifications']['vigilance'] = True
        current['level'] = 3
        await manager._check(1900)
        assert send.await_count == 10


@pytest.mark.asyncio
async def test_failed_recipient_retries_without_resending_successful_target():
    manager, config, send = setup_manager()
    delivered, failed_once = [], False
    async def deliver(domain, service, data, blocking):
        nonlocal failed_once
        if service == 'second' and not failed_once:
            failed_once = True
            raise HomeAssistantError('temporary failure')
        delivered.append(service)
    send.side_effect = deliver
    current = snapshot()
    with patch('custom_components.station_meteo.notifications.current_alerts', side_effect=lambda *args: current):
        await manager._check(1000)
        current = snapshot(3)
        await manager._check(1060)
        assert delivered == ['first'] and manager.vigilance_pending
        await manager._check(1120)
        assert delivered == ['first', 'second'] and manager.vigilance_pending is None
        await manager._check(1180)
        assert send.await_count == 3
