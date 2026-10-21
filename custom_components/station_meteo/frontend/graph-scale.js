/* Readable bounds in display units. Rain histograms keep their own scale. */
export function gaugeScale(role,values,unit=''){
 let minimum=Infinity,maximum=-Infinity;
 for(const value of values){if(typeof value!=='number'||!Number.isFinite(value))continue;minimum=Math.min(minimum,value);maximum=Math.max(maximum,value);}
 if(minimum===Infinity){minimum=0;maximum=0;}
 const margins={temperature:10,humidity:50,pressure:10,uv:2,irradiance:100};
 const wind=role==='wind_speed'||role==='wind_gust';
 const margin=wind?(unit==='m/s'?10/3.6:10):(margins[role]??Math.max(1,(maximum-minimum)*.1));
 let lower=minimum-margin,upper=maximum+margin;
 if(['humidity','uv','irradiance','wind_speed','wind_gust'].includes(role))lower=Math.min(minimum,Math.max(0,lower));
 if(role==='humidity')upper=Math.max(maximum,Math.min(100,upper));
 // A malformed reading outside a physical range must not collapse the axis.
 if(upper<=lower)upper=lower+Math.max(1,margin);
 return {lower,upper};
}
