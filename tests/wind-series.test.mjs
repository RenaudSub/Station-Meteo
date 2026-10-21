import assert from 'node:assert/strict';
import {windOverview} from '../custom_components/station_meteo/frontend/wind-series.js';
const Q=900000;
let result=windOverview([{t:0,v:0},{t:Q/10,v:10}],0,Q);
assert.equal(result.length,1);assert.equal(result[0].v,9);assert.equal(result[0].t,Q/2);
assert.equal(windOverview([{t:0,v:0},{t:Q/10,v:10}],0,Q,true)[0].v,10);
// Rapid alternation yields one honest peak per quarter, not hundreds of spikes.
const raw=Array.from({length:3600},(_,i)=>({t:i*1000,v:i%2?7:0}));
const peaks=windOverview(raw,0,4*Q,true);assert.equal(peaks.length,4);assert(peaks.every(p=>p.v===7));
const means=windOverview(raw,0,4*Q);assert(means.every(p=>p.v===3.5));
// Unknown intervals remain gaps, including a fully missing quarter.
result=windOverview([{t:-Q,v:4},{t:Q,v:null},{t:2*Q,v:6}],0,3*Q);
assert.deepEqual(result.map(p=>p.v),[4,null,6]);
assert(windOverview([],0,2*Q).every(p=>p.v===null));
assert.deepEqual(windOverview([],10,10),[]);
result=windOverview([{t:0,v:2},{t:Q/2,v:4},{t:Q/2,v:5},{t:2*Q,v:999}],Q/4,Q*3/4);
assert.equal(result.length,1);assert.equal(result[0].v,3.5); // duplicate timestamp: last observation wins; future excluded
console.log('Wind overview passed: weighted means, exact peaks, dense readings, gaps, baseline, partial intervals, duplicates and future exclusion.');
