import assert from 'node:assert/strict';
import {hourlyRainFromCounter,localHourStart,HOUR,rainScale} from '../custom_components/station_meteo/frontend/rain-history.js';
const stamp=s=>Date.parse(s),zone='Europe/Paris',now=stamp('2026-10-17T12:50:00Z'),start=localHourStart(now,zone);
let cases=0;
function test(name,fn){fn();console.log('OK '+name);cases++;}
function hourly(rows,current={v:rows.at(-1)?.v,t:rows.at(-1)?.t},time=now,tz=zone){return hourlyRainFromCounter(rows,current,time,tz);}
function value(rows,t){return rows.points.find(p=>p.t===stamp(t))?.v;}
test('Hourly amounts and current partial hour use the same zero/max values',()=>{
 const data=hourly([{t:start-13*HOUR,v:10},{t:start-1.5*HOUR,v:10.3},{t:start-20*60000,v:10.5},{t:start+20*60000,v:10.6}]);
 assert.equal(data.points.length,12);assert.equal(value(data,'2026-10-17T10:00:00Z'),.3);assert.equal(value(data,'2026-10-17T11:00:00Z'),.2);assert.equal(value(data,'2026-10-17T12:00:00Z'),.1);
 assert.equal(data.points.at(-1).partial,true);assert.equal(data.points.at(-1).end,now);assert.equal(Math.min(...data.points.map(p=>p.v)),0);assert.equal(Math.max(...data.points.map(p=>p.v)),.3);
});
test('A constant counter with one old recorded state yields twelve real dry intervals',()=>{
 const data=hourly([{t:start-20*HOUR,v:.3}]);assert.equal(data.points.length,12);assert(data.points.every(p=>p.v===0));
});
test('No recorded history or missing hourly baseline does not invent dry weather',()=>{
 assert.equal(hourly([],{v:.3,t:start-20*HOUR}).points.length,0);
 assert.equal(hourly([{t:start+5*60000,v:.3}]).points.length,0);
});
test('Zero reset and reset to a positive amount never produce a negative spike',()=>{
 let data=hourly([{t:start-HOUR,v:20},{t:start+10*60000,v:20.1},{t:start+20*60000,v:0},{t:start+30*60000,v:.2}]);assert.equal(data.points.at(-1).v,.3);
 data=hourly([{t:start-HOUR,v:20},{t:start+20*60000,v:.2},{t:start+30*60000,v:.3}]);assert.equal(data.points.at(-1).v,.3);
});
test('Unavailable periods are omitted and not bridged; valid later hours recover',()=>{
 const data=hourly([{t:start-5*HOUR,v:1},{t:start-3.5*HOUR,v:null},{t:start-2.5*HOUR,v:1.8},{t:start-HOUR,v:2}]);
 assert(!data.points.some(p=>p.t===start-4*HOUR));assert(!data.points.some(p=>p.t===start-3*HOUR));assert(data.points.some(p=>p.t===start-2*HOUR));
 assert.equal(hourly([{t:start-HOUR,v:1}],{v:null,t:start+10*60000}).points.length,1);
});
test('An exact clock-boundary reading is counted only in the interval it closes',()=>{
 const data=hourly([{t:start-2*HOUR,v:1},{t:start,v:1.3}]);assert.equal(data.points.find(p=>p.t===start-HOUR).v,.3);assert.equal(data.points.at(-1).v,0);
});
test('Future, nonnumeric and negative counter values cannot fabricate rainfall',()=>{
 const data=hourly([{t:start-2*HOUR,v:0},{t:start+5*60000,v:-1},{t:now+HOUR,v:100}],{v:0,t:now});assert(!data.points.some(p=>p.t===start));assert(!data.points.some(p=>p.v>0));
});
test('Current HA value is attributed to its change time before the current clock hour',()=>{
 const data=hourly([{t:start-3*HOUR,v:1}],{v:1.3,t:start-5*60000});assert.equal(data.points.find(p=>p.t===start-HOUR).v,.3);assert.equal(data.points.at(-1).v,0);
});
test('Without a current entity state, unobserved end intervals stay unavailable',()=>{
 const data=hourly([{t:start-3*HOUR,v:0},{t:start-HOUR,v:.3}],null);assert(!data.points.some(p=>p.t===start));assert(!data.points.some(p=>p.t===start-HOUR));
});
test('Clock hours align with nonintegral time zones',()=>{
 const t=stamp('2026-10-17T12:50:15.125Z');assert.equal(localHourStart(t,'Asia/Kathmandu'),stamp('2026-10-17T12:15:00Z'));
});
test('Paris DST repeated hours remain separate real intervals',()=>{
 const t=stamp('2026-10-25T02:30:00Z'),data=hourly([{t:t-15*HOUR,v:0},{t:stamp('2026-10-25T00:30:00Z'),v:.3},{t:stamp('2026-10-25T01:30:00Z'),v:.5}],undefined,t);
 assert.equal(data.points.length,12);assert.equal(value(data,'2026-10-25T00:00:00Z'),.3);assert.equal(value(data,'2026-10-25T01:00:00Z'),.2);
});
test('Rain axis steps remain readable for submillimetre amounts',()=>{const s=rainScale(.3);assert.equal(s.upper,.4);assert.equal(s.digits,1);const small=rainScale(.1);assert.equal(small.upper,.2);assert.equal(small.digits,2);assert(rainScale(25).upper>=25);});
console.log(`${cases} hourly-rain cases passed.`);
