"""Generate browser API fixtures with the real durable aggregation engine."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from copy import deepcopy
import json
from homeassistant.core import State
from custom_components.station_meteo.archive import ArchiveService, boundaries, sources
from custom_components.station_meteo.const import DEFAULT_CONFIG

async def main():
    with TemporaryDirectory() as folder:
        cfg=deepcopy(DEFAULT_CONFIG)
        cfg['entities']={role:'sensor.test_'+role for role in ['rain_total','temperature','humidity','uv','irradiance','pressure','wind_speed','wind_gust']}
        hass=SimpleNamespace(config=SimpleNamespace(path=lambda *p:str(Path(folder).joinpath(*p)),time_zone='Europe/Paris',components=set()),states=SimpleNamespace(get=lambda eid:None),async_add_executor_job=lambda f,*args:asyncio.to_thread(f,*args))
        s=ArchiveService(hass,{'config':cfg});s.store.initialize();s.status='ready'
        for offset in range(70):
            day=date(2026,10,17)-timedelta(days=offset);start,end=boundaries(day,'Europe/Paris')
            for source in sources(cfg):
                values={'rain':(100-offset,100-offset+.3,100-offset+.4),'temperature':(10,20,12),'humidity':(60,40,70),'uv':(0,5,0),'irradiance':(0,600,0),'pressure':(1010,1012,1011),'wind_speed':(1,3,2),'wind_gust':(2,8,4)}[source.role]
                unit={'rain':'mm','temperature':'°C','humidity':'%','uv':'','irradiance':'W/m²','pressure':'hPa','wind_speed':'m/s','wind_gust':'m/s'}[source.role]
                states=[State(source.entity,str(v),{'unit_of_measurement':unit},last_updated=datetime.fromtimestamp(t,timezone.utc)) for t,v in zip([start,start+8*3600,start+20*3600],values)]
                s.store.import_series(source,states,start,end,'Europe/Paris')
        s.store.flush();out={}
        for day in [date(2026,10,17),date(2026,10,16),date(2026,10,10),date(2026,10,9),date(2026,10,3),date(2026,9,10)]:
            for role in ['rain','temperature','humidity','uv','irradiance','pressure','wind_speed']:
                for scale in ['hour','week','month']:
                    out[f'{role}/{day}/{scale}']=await s.query(role,day,scale)
        Path('/tmp/archive-fixture.json').write_text(json.dumps(out))
        print('Durable backend fixtures generated:',len(out))
asyncio.run(main())
