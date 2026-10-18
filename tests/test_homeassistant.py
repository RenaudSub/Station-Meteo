"""Smoke tests using real Home Assistant APIs; no physical station is required."""
import asyncio
from types import SimpleNamespace
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.components import frontend
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import device_registry as dr, entity_registry as er
from custom_components.station_meteo import async_setup_entry, async_unload_entry
from custom_components.station_meteo.const import DEFAULT_CONFIG
from custom_components.station_meteo.websocket import catalog, validate_config


def make_entry(domain='station_meteo'):
    return ConfigEntry(version=1,minor_version=1,domain=domain,title='Station Météo',data={},options={},source='user',unique_id=domain,discovery_keys={},subentries_data=[])

@pytest.mark.asyncio
async def test_panel_catalog_storage_and_permissions(tmp_path):
    hass=HomeAssistant(str(tmp_path))
    hass.config_entries=ConfigEntries(hass,{})
    await hass.config_entries.async_initialize()
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    paths=[]
    views=[]
    async def static(configs):paths.extend(configs)
    hass.http=SimpleNamespace(async_register_static_paths=static,register_view=views.append)
    entry=make_entry()
    hass.config_entries._entries[entry.entry_id]=entry
    try:
        assert await async_setup_entry(hass,entry)
        assert paths[0].url_path=='/station_meteo/frontend'
        assert len(views)==1
        assert views[0].requires_auth
        assert paths[1].url_path=='/station_meteo/images'
        assert frontend.DATA_PANELS in hass.data
        assert 'station-meteo' in hass.data[frontend.DATA_PANELS]
        blu=make_entry('bthome')
        hass.config_entries._entries[blu.entry_id]=blu
        device=dr.async_get(hass).async_get_or_create(config_entry_id=blu.entry_id,identifiers={('bthome','C0:2C:ED:95:D6:93')},name='SBWS-90CM D693',model='SBWS-90CM')
        registry=er.async_get(hass)
        for idx in (1,2):
            e=registry.async_get_or_create('sensor','bthome',f'C0:2C:ED:95:D6:93-speed_{idx}',device_id=device.id,config_entry=blu,original_device_class='speed',suggested_object_id=f'exterieur_station_meteo_vitesse_{idx}')
            hass.states.async_set(e.entity_id,idx,{'device_class':'speed','unit_of_measurement':'m/s'})
        assert validate_config(hass,{**DEFAULT_CONFIG,'background_url':'https://example.com/photo.jpg'})['background_url']=='https://example.com/photo.jpg'
        assert validate_config(hass,{**DEFAULT_CONFIG,'background_url':'/local/photo.jpg'})['background_url']=='/local/photo.jpg'
        assert validate_config(hass,{**DEFAULT_CONFIG,'weather_icons':{'cloudy':'/station_meteo/images/cloud.webp'}})['weather_icons']['cloudy'].endswith('cloud.webp')
        for icons in ({'cloudy':'javascript:alert(1)'}, {'cloudy':'/local/../api/config'}, {'unknown':'/local/x.png'}, [], {'cloudy':42}):
            with pytest.raises(ValueError): validate_config(hass,{**DEFAULT_CONFIG,'weather_icons':icons})
        assert validate_config(hass,{**DEFAULT_CONFIG,'compass_url':'/local/rose.webp','arrow_url':'/station_meteo/images/arrow.svg'})['arrow_url'].endswith('.svg')
        for key in ('compass_url','arrow_url'):
            with pytest.raises(ValueError):validate_config(hass,{**DEFAULT_CONFIG,key:'javascript:alert(1)'})
        found=catalog(hass)
        assert found[0]['mapping']['wind_speed'].endswith('_1')
        assert found[0]['mapping']['wind_gust'].endswith('_2')
        config={**DEFAULT_CONFIG,'entities':{'wind_speed':found[0]['mapping']['wind_speed']}}
        valid=validate_config(hass,config)
        await hass.data['station_meteo']['store'].async_save(valid)
        # Actual admin decorator rejects a non-admin before settings can change.
        handler,_=hass.data['websocket_api']['station_meteo/save']
        with pytest.raises(Unauthorized):
            handler(hass,SimpleNamespace(user=SimpleNamespace(is_admin=False)),{'id':1,'type':'station_meteo/save','config':valid})
        for endpoint in ('station_meteo/almanac','station_meteo/almanac_save'):
            protected,_=hass.data['websocket_api'][endpoint]
            with pytest.raises(Unauthorized):
                protected(hass,SimpleNamespace(user=SimpleNamespace(is_admin=False)),{'id':2,'type':endpoint})
        assert (tmp_path/'station_meteo'/'almanac'/'saints.json').is_file()
        assert (tmp_path/'station_meteo'/'almanac'/'citations.json').is_file()
        assert (tmp_path/'station_meteo'/'almanac'/'dictons.json').is_file()
        assert await async_unload_entry(hass,entry)
        assert 'station-meteo' not in hass.data[frontend.DATA_PANELS]
        assert await async_setup_entry(hass,entry)
        assert len(paths)==2  # reload never duplicates static routes
        assert await hass.data['station_meteo']['store'].async_load()==valid
        for bad in [{'background_url':'javascript:alert(1)'},{'background_url':'http://example.com/image.jpg'},{'background_url':'/local/../api/config'}, {'language':'xx'},{'altitude':float('nan')},{'entities':{'temperature':'weather.foo'}},{'entities':{'oops':'sensor.x'}}]:
            with pytest.raises(ValueError):validate_config(hass,{**DEFAULT_CONFIG,**bad})
    finally:
        await hass.async_stop(force=True)
