"""Exercise real BTHome packets, including duplicate speed indexes."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from bthome_ble import BTHomeBluetoothDeviceData

FILE = Path(__file__).parents[1] / 'custom_components/station_meteo/mapping.py'
spec = importlib.util.spec_from_file_location('mapping', FILE)
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)


def packet_entities():
    # Shelly's documented packet 1 and packet 2 (sample data, unencrypted BTHome v2).
    packets = ['40056400002000445A0044FA0046145E883B',
               '40016404DC810108FC030CA00F2E2945F3005F0000']
    data = BTHomeBluetoothDeviceData()
    entries = {}
    for raw in packets:
        info = SimpleNamespace(name='SBWS-90CM',address='C0:2C:ED:95:D6:93',rssi=-70,
          manufacturer_data={},service_data={'0000fcd2-0000-1000-8000-00805f9b34fb':bytes.fromhex(raw)},
          service_uuids=[],source='test',time=1)
        result = data.update(info)
        for key,desc in result.entity_descriptions.items():
            eid = 'sensor.exterieur_station_meteo_'+key.key
            entries[eid] = dict(entity_id=eid, unique_id='C0:2C:ED:95:D6:93-'+key.key,
               device_class=str(desc.device_class), translation_key='', disabled=False)
        for key,desc in result.binary_entity_descriptions.items():
            eid='binary_sensor.exterieur_station_meteo_'+key.key
            entries[eid]=dict(entity_id=eid,unique_id='C0:2C:ED:95:D6:93-'+key.key,
               device_class=str(desc.device_class),translation_key='',disabled=False)
    return list(entries.values())


def test_actual_ws90_packet_mapping():
    result,ambiguous=mapping.map_entities(packet_entities())
    assert result['wind_speed'].endswith('speed_1')
    assert result['wind_gust'].endswith('speed_2')
    assert result['temperature'].endswith('temperature')
    assert result['rain_status'].startswith('binary_sensor.')
    assert result['humidity'].startswith('sensor.')
    assert result['uv'].endswith('uv_index')
    assert result['rain_total'].endswith('precipitation')
    assert 'voltage' not in result
    assert not ambiguous


def test_names_and_values_do_not_change_mapping():
    entries=packet_entities()
    for e in entries:e.update(name='Humidité',state='unavailable')
    result,_=mapping.map_entities(entries)
    assert result['wind_gust'].endswith('speed_2')
    assert result['rain_status'].startswith('binary_sensor.')


def test_disabled_and_ambiguous_speed_are_not_guessed():
    entries=[dict(entity_id='sensor.a',unique_id='mac-speed',device_class='speed',disabled=False),
             dict(entity_id='sensor.b',unique_id='mac-temperature',device_class='temperature',disabled=True)]
    result,ambiguous=mapping.map_entities(entries)
    assert not result
    assert ambiguous==['sensor.a']
