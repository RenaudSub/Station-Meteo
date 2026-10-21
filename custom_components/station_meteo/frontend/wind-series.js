/* Display-only 15-minute overview. Keep means duration weighted and gust
 * peaks exact; unavailable intervals stay gaps rather than invented zeros. */
const QUARTER=900000;
export function windOverview(points,start,end,peak=false){
 if(!(end>start))return [];
 const samples=new Map();
 for(const p of points)if(Number.isFinite(p.t)&&p.t<=end)samples.set(p.t,Number.isFinite(p.v)?p.v:null);
 const sorted=[...samples].sort((a,b)=>a[0]-b[0]);
 const buckets=new Map();
 for(let stamp=Math.floor(start/QUARTER)*QUARTER;stamp<end;stamp+=QUARTER)buckets.set(stamp,{integral:0,seconds:0,max:null});
 for(let i=0;i<sorted.length;i++){
  const [t,value]=sorted[i];if(value==null)continue;
  let begin=Math.max(start,t);const finish=Math.min(end,sorted[i+1]?.[0]??end);
  while(begin<finish){
   const stamp=Math.floor(begin/QUARTER)*QUARTER,stop=Math.min(finish,stamp+QUARTER),row=buckets.get(stamp),duration=stop-begin;
   row.integral+=value*duration;row.seconds+=duration;row.max=row.max==null?value:Math.max(row.max,value);begin=stop;
  }
 }
 return [...buckets].map(([t,row])=>({t:(Math.max(start,t)+Math.min(end,t+QUARTER))/2,v:row.seconds?(peak?row.max:row.integral/row.seconds):null}));
}
