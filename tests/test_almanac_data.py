"""Complete calendars, durable customization, external edits and safe saves."""
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pytest
from custom_components.station_meteo.almanac_data import LocalAlmanac, DATE_KEYS, KINDS, validate_calendar
from custom_components.station_meteo.ephemeris import astronomy


def initialized(tmp_path):
    result=LocalAlmanac(tmp_path/'almanac');result.initialize();return result


def test_defaults_all_dates_and_texts_unique(tmp_path):
    service=initialized(tmp_path)
    for kind in KINDS:
        entries=service.read(kind)['entries']
        assert len(entries)==366 and set(entries)==DATE_KEYS
        assert sum(key.startswith('02-') for key in entries)==29
        assert not service.read(kind)['warning']
        for year in (2026,2028):
            for month in range(1,13):
                for day in range(1,monthrange(year,month)[1]+1):
                    assert service.daily(date(year,month,day))['quote']
        if kind!='saints':
            texts=[v['text'] if isinstance(v,dict) else v for v in entries.values()]
            assert len(set(texts))==366
    assert service.daily(date(2026,12,25))['saint']=='Noël'


def test_edit_saved_manual_changes_reload_and_updates_survive(tmp_path):
    service=initialized(tmp_path);model=service.editors()['citations']
    edited=deepcopy(model['entries']);edited['10-15']={'text':'Mon texte personnel <b>reste du texte</b>.','author':'Mon auteur'}
    saved=service.save('citations',edited,model['revision'])
    assert saved['revision']!=model['revision']
    service.initialize()  # An integration update/restart must not overwrite custom files.
    assert service.daily(date(2026,10,15))['quote']==edited['10-15']['text']
    assert service.daily(date(2026,10,15))['quote_author']=='Mon auteur'
    path=service.directory/'dictons.json';data=json.loads(path.read_text());data['10-15']='Mon dicton du fichier.';path.write_text(json.dumps(data))
    assert service.daily(date(2026,10,15))['saying']=='Mon dicton du fichier.'
    newer=LocalAlmanac(service.directory);newer.initialize()
    assert newer.daily(date(2026,10,15))['saying']=='Mon dicton du fichier.'


def test_conflict_validation_and_atomic_failure_keep_existing_file(tmp_path):
    service=initialized(tmp_path);model=service.read('dictons')
    first=deepcopy(model['entries']);first['10-15']='Première modification.'
    service.save('dictons',first,model['revision'])
    with pytest.raises(ValueError,match='almanac_conflict'):service.save('dictons',model['entries'],model['revision'])
    current=service.read('dictons');path=service.directory/'dictons.json';before=path.read_bytes()
    edited=deepcopy(first);edited['10-15']='Autre modification.'
    with patch('custom_components.station_meteo.almanac_data.os.replace',side_effect=OSError('test disk error')):
        with pytest.raises(OSError):service.save('dictons',edited,current['revision'])
    assert path.read_bytes()==before
    assert not list(service.directory.glob('.almanac-*.tmp'))
    for invalid in ({}, {**first,'13-01':'invalide'}, {**first,'10-15':''}, {**first,'10-15':'x'*601}):
        with pytest.raises(ValueError):validate_calendar('dictons',invalid)
    with pytest.raises(ValueError):service.save('../saints',first,current['revision'])


def test_invalid_file_falls_back_without_overwriting_and_can_be_repaired(tmp_path):
    service=initialized(tmp_path);path=service.directory/'citations.json';path.write_text('{invalide')
    model=service.editors()['citations'];assert model['warning']
    assert service.daily(date(2026,10,15))['quote']
    assert path.read_text()=='{invalide'
    service.save('citations',model['entries'],model['revision'])
    assert not service.read('citations')['warning']


def test_local_midnight_and_february_do_not_shift_march(tmp_path):
    service=initialized(tmp_path)
    hass=SimpleNamespace(config=SimpleNamespace(latitude=42.6,longitude=2.6,time_zone='Europe/Paris'))
    sky=astronomy(hass,{'altitude':247},datetime(2026,12,31,23,5,tzinfo=timezone.utc))
    assert sky['date']=='2027-01-01'
    assert service.daily(date(2027,3,1))['quote']==service.daily(date(2028,3,1))['quote']
    assert service.daily(date(2028,2,29))['quote']!=service.daily(date(2028,3,1))['quote']
