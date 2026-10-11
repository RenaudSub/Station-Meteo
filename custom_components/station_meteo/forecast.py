"""Primary forecasts completed by same-slot fallback data, in common units."""
import asyncio
from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

NUMERIC = {'temperature','templow','apparent_temperature','precipitation','precipitation_probability','wind_speed','wind_gust_speed','wind_bearing','humidity','uv_index','cloud_coverage'}
NONNEGATIVE = NUMERIC - {'temperature','templow','apparent_temperature'}
FIELDS = NUMERIC | {'condition'}


def valid_value(key, value):
    if key == 'condition':
        return isinstance(value, str) and value not in ('','unknown','unavailable')
    return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) and (key not in NONNEGATIVE or value >= 0) and (key not in {'humidity','precipitation_probability','cloud_coverage'} or value <= 100)


def normalize(rows, attributes, entity_id):
    result=[]
    for row in rows:
        if not isinstance(row,dict):continue
        date=dt_util.parse_datetime(str(row.get('datetime','')))
        if date is None or date.tzinfo is None:continue
        item={'datetime':date.isoformat(),'_sources':{}}
        for key in FIELDS:
            value=row.get(key)
            if not valid_value(key,value):continue
            if key in {'temperature','templow','apparent_temperature'}:
                unit=str(attributes.get('temperature_unit','°C')).lower()
                if 'f' in unit:value=(value-32)*5/9
                elif unit=='k':value-=273.15
            elif key in {'wind_speed','wind_gust_speed'}:
                unit=str(attributes.get('wind_speed_unit','km/h')).lower()
                value*= {'m/s':3.6,'mph':1.609344,'kn':1.852,'kt':1.852,'knots':1.852}.get(unit,1)
            elif key=='precipitation' and str(attributes.get('precipitation_unit','mm')).lower()=='in':value*=25.4
            item[key]=value
            item['_sources'][key]=entity_id
        if item['_sources']:result.append(item)
    return result


def merge_rows(primary, fallback, kind, now, time_zone):
    """Merge only matching UTC hours or matching local calendar days; preserve zeros."""
    zone=ZoneInfo(time_zone)
    today=datetime.fromtimestamp(now,timezone.utc).astimezone(zone).date()
    def slot(row):
        date=dt_util.parse_datetime(row['datetime'])
        return int(date.timestamp()//3600) if kind=='hourly' else date.astimezone(zone).date()
    def eligible(row):
        date=dt_util.parse_datetime(row['datetime'])
        return date.timestamp()//3600 >= now//3600 if kind=='hourly' else date.astimezone(zone).date() >= today
    backup={slot(row):row for row in fallback if eligible(row)}
    preferred={slot(row):row for row in primary if eligible(row)}
    result=[]
    for key in sorted(set(preferred)|set(backup)):
        p,b=preferred.get(key),backup.get(key)
        if p is None:result.append(b);continue
        out={**p,'_sources':dict(p['_sources'])}
        if b:
            for field in FIELDS:
                if field not in out and field in b:
                    out[field]=b[field]
                    out['_sources'][field]=b['_sources'][field]
        result.append(out)
    return result


async def async_forecasts(hass, cfg, now=None, kinds=('hourly','daily')):
    now=dt_util.utcnow().timestamp() if now is None else now
    entities=cfg.get('entities',{})
    ids=list(dict.fromkeys(eid for eid in (entities.get('weather'),entities.get('weather_fallback')) if eid))
    sources={}
    errors=[]
    async def read(eid,kind):
        state=hass.states.get(eid)
        bit=2 if kind=='hourly' else 1
        if state is None or state.state in ('unknown','unavailable','') or not int(state.attributes.get('supported_features',0))&bit:return []
        try:
            response=await hass.services.async_call('weather','get_forecasts',{'type':kind,'entity_id':eid},blocking=True,return_response=True)
            rows=(response or {}).get(eid,{}).get('forecast',[])
            return normalize(rows if isinstance(rows,list) else [],state.attributes,eid)
        except HomeAssistantError:
            errors.append(eid)
            return []
    requests=[(eid,kind) for eid in ids for kind in kinds]
    values=await asyncio.gather(*(read(eid,kind) for eid,kind in requests))
    data=dict(zip(requests,values))
    for eid in ids:
        state=hass.states.get(eid)
        sources[eid]=(state.attributes.get('friendly_name') if state else None) or eid
    primary=entities.get('weather');fallback=entities.get('weather_fallback')
    result={kind:merge_rows(data.get((primary,kind),[]),data.get((fallback,kind),[]),kind,now,hass.config.time_zone) for kind in kinds}
    result.update(sources=sources,units={'temperature':'°C','wind_speed':'km/h','precipitation':'mm'},errors=list(set(errors)))
    return result
