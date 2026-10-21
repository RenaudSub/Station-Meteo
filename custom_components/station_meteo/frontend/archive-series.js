/* Smooth interpolation only: values and extrema at observations stay exact.
 * Identical Bezier handles for mean/min/max prevent crossing or overshoot. */
export function archiveSeries(points,x,y,smooth=true){
 const groups=[];let group=[];
 for(let i=0;i<points.length;i++){
  const p=points[i];
  if(p.value==null){if(group.length)groups.push(group);group=[];continue;}
  group.push({x:x(i),mean:y(p.value),low:y(p.min??p.value),high:y(p.max??p.value)});
 }
 if(group.length)groups.push(group);
 const curve=(rows,key)=>rows.map((p,i)=>{if(!i)return `M${p.x},${p[key]}`;if(!smooth)return `L${p.x},${p[key]}`;const a=rows[i-1],dx=(p.x-a.x)/3;return `C${a.x+dx},${a[key]} ${p.x-dx},${p[key]} ${p.x},${p[key]}`;}).join(' ');
 return groups.map(rows=>({mean:curve(rows,'mean'),band:rows.length<2?'':curve(rows,'high')+' L'+curve([...rows].reverse(),'low').slice(1)+' Z'}));
}
