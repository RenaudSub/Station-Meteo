/* Hourly amounts from a cumulative rain counter, never instantaneous intensity. */
export const HOUR=3600000;
export function localHourStart(now,timeZone){
 const parts=new Intl.DateTimeFormat('en-GB',{timeZone,minute:'2-digit',second:'2-digit'}).formatToParts(new Date(now));
 const value=type=>Number(parts.find(p=>p.type===type)?.value||0);
 return now-value('minute')*60000-value('second')*1000-((now%1000)+1000)%1000;
}
export function hourlyRainFromCounter(raw,current,now,timeZone,count=12){
 const currentStart=localHourStart(now,timeZone),start=currentStart-(count-1)*HOUR;
 const result={points:[],start,end:currentStart+HOUR,currentStart};
 const valid=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
 const rows=(raw||[]).filter(p=>Number.isFinite(p.t)&&p.t<=now).map(p=>({t:p.t,v:valid(p.v)?p.v:null}));
 // A current value alone is not a recorded history or an hourly baseline.
 if(!rows.length)return result;
 rows.sort((a,b)=>a.t-b.t);
 if(current){
  const last=rows.at(-1),t=Number.isFinite(current.t)&&current.t>=last.t&&current.t<=now?current.t:now;
  rows.push({t,v:valid(current.v)?current.v:null},{t:now,v:valid(current.v)?current.v:null});
 }
 const samples=[...new Map(rows.map(p=>[p.t,p])).values()].sort((a,b)=>a.t-b.t);
 const observedEnd=samples.at(-1).t;
 for(let i=0;i<count;i++){
  const t=start+i*HOUR,end=Math.min(t+HOUR,now);
  if(end>observedEnd)continue;
  let baseline=null;
  for(const p of samples){if(p.t>t)break;baseline=p;}
  if(!baseline||baseline.v===null)continue;
  let previous=baseline.v,amount=0,complete=true;
  for(const p of samples){
   if(p.t<=t)continue;if(p.t>end)break;
   if(p.v===null){complete=false;break;}
   // A lower counter is a reset; add only the new accumulation after reset.
   amount+=p.v>=previous?p.v-previous:p.v;previous=p.v;
  }
  if(complete)result.points.push({t,end,v:Number(amount.toFixed(6)),partial:end<t+HOUR});
 }
 return result;
}
export function rainScale(maximum){
 const target=(maximum>0?maximum:.4)/4,power=10**Math.floor(Math.log10(target));
 const step=[1,2,5,10].find(n=>n*power>=target-1e-12)*power;
 return {upper:step*4,digits:Math.min(6,Math.max(1,-Math.floor(Math.log10(step))))};
}
