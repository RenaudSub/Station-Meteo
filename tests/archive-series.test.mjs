import assert from 'node:assert/strict';
import {archiveSeries} from '../custom_components/station_meteo/frontend/archive-series.js';
const points=[{value:10,min:2,max:15},{value:30,min:20,max:36},{value:15,min:5,max:22}];
const curves=archiveSeries(points,i=>i*30,v=>100-v);
assert.equal(curves.length,1);assert.match(curves[0].mean,/^M0,90 C10,90 20,70 30,70 C40,70 50,85 60,85$/);assert.match(curves[0].band,/Z$/);
// Cubic interpolation remains between the observations and the two bounds.
for(let i=1;i<points.length;i++)for(let step=0;step<=100;step++){
 const t=step/100,w=3*t*t-2*t*t*t,a=points[i-1],b=points[i];
 const mean=a.value*(1-w)+b.value*w,min=a.min*(1-w)+b.min*w,max=a.max*(1-w)+b.max*w;
 assert(mean>=min-1e-9&&mean<=max+1e-9);assert(mean>=Math.min(a.value,b.value)-1e-9&&mean<=Math.max(a.value,b.value)+1e-9);
}
const split=archiveSeries([points[0],{value:null},points[1],points[2]],i=>i,v=>v);assert.equal(split.length,2);assert.equal(split[0].band,'');assert.match(split[1].mean,/^M2,30 /);
assert.deepEqual(archiveSeries([{value:null}],i=>i,v=>v),[]);
assert.equal(archiveSeries([{value:2}],i=>i,v=>v)[0].mean,'M0,2');
console.log('Archive smoothing passed: exact mean points, monotone bounds, no overshoot, no bridging missing data, isolated and empty series.');

const straight=archiveSeries(points,i=>i*30,v=>100-v,false);
assert.match(straight[0].mean,/L/);assert.doesNotMatch(straight[0].mean,/C/);
assert.match(straight[0].band,/Z$/);assert.equal(points[1].value,30);
