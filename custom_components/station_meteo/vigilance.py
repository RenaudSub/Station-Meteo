"""Read the official Météo-France integration's alert sensor, without scraping."""
import re
from datetime import datetime, timezone
from homeassistant.helpers import entity_registry as er

COLORS = {'green':1,'vert':1,'yellow':2,'jaune':2,'orange':3,'red':4,'rouge':4}


def color(value):
    return COLORS.get(str(value).strip().casefold(), 0)


def alert_snapshot(state, department=None, now=None):
    now = now or datetime.now(timezone.utc)
    result = {'entity_id':state.entity_id if state else None,'department':department,
              'status':'unavailable','level':0,'phenomena':[], 'received':None,
              'source':'https://vigilance.meteofrance.fr/fr/pyrenees-orientales' if department=='66' else 'https://vigilance.meteofrance.fr/fr'}
    if state is None:
        return result
    result['phenomena'] = [{'name':key,'level':color(value)} for key,value in state.attributes.items() if color(value)>1]
    result['level'] = max([color(state.state),*[p['level'] for p in result['phenomena']]])
    if not color(state.state):
        return result
    # last_updated can remain unchanged for days while the alert stays green.
    # last_reported tracks each actual state report from the HA integration.
    reported = getattr(state,'last_reported',None) or state.last_updated
    result['received'] = reported.isoformat()
    result['status'] = 'stale' if (now-reported).total_seconds()>2700 else 'available'
    return result


def current_alerts(hass, runtime):
    registry = er.async_get(hass)
    configured = runtime['config'].get('entities',{}).get('weather_alert')
    candidates = [entry for entry in registry.entities.values() if entry.platform=='meteo_france' and entry.domain=='sensor' and not entry.disabled_by and re.search(r'weather.alert$',str(entry.unique_id),re.I)]
    if configured:
        entry=registry.async_get(configured)
    else:
        weather_entries=[registry.async_get(runtime['config'].get('entities',{}).get(role,'')) for role in ('weather','weather_fallback')]
        config_ids={entry.config_entry_id for entry in weather_entries if entry and entry.platform=='meteo_france'}
        matching=[entry for entry in candidates if entry.config_entry_id in config_ids]
        choices=matching or candidates
        entry=choices[0] if len(choices)==1 else None
        configured=entry.entity_id if entry else None
    if not configured:
        return {'status':'choose' if candidates else 'not_configured','level':0,'phenomena':[], 'entity_id':None,'department':None,'received':None,'source':'https://vigilance.meteofrance.fr/fr'}
    identity=str(entry.unique_id) if entry else ''
    match=re.match(r'^(\d{2,3}|2[AB])\b',identity,re.I)
    department=match.group(1).upper() if match else None
    data=alert_snapshot(hass.states.get(configured),department)
    if data['status']=='available':
        runtime.setdefault('vigilance_last_good',{})[configured]=dict(data)
    elif previous:=runtime.get('vigilance_last_good',{}).get(configured):
        data={**previous,'status':data['status']}
    return data
