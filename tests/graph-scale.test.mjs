import assert from 'node:assert/strict';
import {gaugeScale} from '../custom_components/station_meteo/frontend/graph-scale.js';
assert.deepEqual(gaugeScale('temperature',[10,10.5]),{lower:0,upper:20.5});
assert.deepEqual(gaugeScale('temperature',[-15,-14]),{lower:-25,upper:-4});
assert.deepEqual(gaugeScale('temperature',[10,10]),{lower:0,upper:20});
assert.deepEqual(gaugeScale('temperature',[null,NaN,undefined,10,Infinity]),{lower:0,upper:20});
assert.deepEqual(gaugeScale('humidity',[98,99]),{lower:48,upper:100});
assert.deepEqual(gaugeScale('humidity',[0,1]),{lower:0,upper:51});
assert.deepEqual(gaugeScale('pressure',[1000,1002]),{lower:990,upper:1012});
assert.deepEqual(gaugeScale('uv',[0,.2]),{lower:0,upper:2.2});
assert.deepEqual(gaugeScale('irradiance',[100,110]),{lower:0,upper:210});
assert.deepEqual(gaugeScale('wind_speed',[2,20],'km/h'),{lower:0,upper:30});
const metres=gaugeScale('wind_speed',[1,5],'m/s');assert.equal(metres.lower,0);assert.equal(metres.upper,5+10/3.6);
const invalid=gaugeScale('humidity',[105,110]);assert(invalid.lower<=105&&invalid.upper>=110);
for(const role of ['temperature','humidity','uv','irradiance','pressure','wind_speed']){const axis=gaugeScale(role,[]);assert(Number.isFinite(axis.lower)&&axis.upper>axis.lower);}
console.log('Graph scales passed: fixed margins, flat/negative temperatures, physical limits, invalid/missing values, wind unit conversion.');
