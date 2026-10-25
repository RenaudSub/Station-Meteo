const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const bundled=(await import('/tmp/weather-browser/node_modules/@sparticuz/chromium/build/index.js')).default;
 const browser=await chromium.launch({headless:true,executablePath:'/tmp/weather-chrome-assets/chromium',args:bundled.args});
 try{
  const page=await browser.newPage({viewport:{width:1536,height:1100},hasTouch:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.qaPanel?._ready&&qaPanel.fc.hourly?.length);
  await page.evaluate(async()=>{
   const {boundedMapView}=await import('/station_meteo/frontend/map-navigation.js');
   const q=qaPanel,original=q.hass.callWS;window.navCalls=[];
   q.hass.callWS=async m=>{
    if(m.type!=='station_meteo/meteociel')return original(m);
    navCalls.push(m);const isLightning=m.index===0,maximum=isLightning?6:4,url=new URL(q.cfg.map_buttons[m.index].url);
    const initial={x:Number(url.searchParams.get('x')),y:Number(url.searchParams.get('y')),zoom:Number(url.searchParams.get('zoom'))};
    const v=m.viewport||initial,viewport=boundedMapView({maximum,kind:isLightning?'lightning':'radar'},v.x,v.y,v.zoom);
    return {kind:viewport.kind,viewport,duration:30,credit:'Météociel',backgrounds:[],labels:[],palette:[],frames:Array.from({length:isLightning?1:3},(_,i)=>({time:new Date(Date.now()-(2-i)*300000).toISOString(),tiles:[],points:isLightning?[{id:'historical',x:384,y:384,age:10}]:[]}))};
   };
  });
  const p=page.locator('station-meteo-panel');
  assert.equal(await p.locator('[data-map-index="0"]').innerText(),'Impacts de foudre');
  assert.equal(await p.locator('[data-map-index="1"]').innerText(),'Radar Pluie/Neige');
  assert.equal(await page.evaluate(()=>qaPanel.cfg.map_buttons[1].url),'https://www.meteociel.fr/observations-meteo/radar2.php?region=so&mode=1');
  const ready=async()=>{await p.locator('canvas.native-weather-map').waitFor();await p.locator('[data-action="map-zoom-out"]:enabled').waitFor();};
  for(const index of [0,6]){
   await page.setViewportSize({width:1536,height:1100});
   await p.locator(`.map-buttons [data-map-index="${index}"]`).click();await ready();
   const initial=await page.evaluate(()=>({...qaPanel._mapView}));
   await p.locator('[data-action="map-zoom-out"]').click();await page.waitForFunction(z=>qaPanel._mapRenderedView.zoom<z,initial.zoom);await ready();
   let before=await page.evaluate(()=>({...qaPanel._mapView}));
   const stage=p.locator('.navigable-map'),box=await stage.boundingBox();
   await page.mouse.move(box.x+box.width*.45,box.y+box.height*.45);await page.mouse.wheel(0,-120);
   await page.waitForFunction(z=>qaPanel._mapRenderedView.zoom>z,before.zoom);await ready();
   before=await page.evaluate(()=>({...qaPanel._mapView}));
   await page.mouse.move(box.x+box.width*.45,box.y+box.height*.45);await page.mouse.down();await page.mouse.move(box.x+box.width*.60,box.y+box.height*.52,{steps:8});await page.mouse.up();
   await page.waitForFunction(x=>Math.abs(qaPanel._mapRenderedView.x-x)>1,before.x);await ready();
   const moved=await page.evaluate(()=>({...qaPanel._mapView}));assert(moved.x<before.x);assert(moved.y<before.y);
   await p.locator('[data-action="map-refresh"]').click();await ready();
   assert.equal(await page.evaluate(()=>qaPanel._mapView.x),moved.x);
   if(index===6)assert(await page.evaluate(()=>!!qaPanel._satTimer));
   await p.locator('[data-action="map-reset-view"]').click();await page.waitForFunction(x=>qaPanel._mapRenderedView.x===x,initial.x);await ready();
   assert.equal(await page.evaluate(()=>qaPanel._mapView.zoom),initial.zoom);
   await page.setViewportSize({width:390,height:1000});
   await p.locator('[data-action="map-zoom-out"]').click();await page.waitForFunction(z=>qaPanel._mapRenderedView.zoom<z,initial.zoom);await ready();
   before=await page.evaluate(()=>({...qaPanel._mapView}));
   await stage.scrollIntoViewIfNeeded();const mobile=await stage.boundingBox(),x=mobile.x+mobile.width/2,y=mobile.y+mobile.height/2;
   const cdp=await page.context().newCDPSession(page);
   await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:x-35,y,id:1},{x:x+35,y,id:2}]});
   await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-70,y,id:1},{x:x+70,y,id:2}]});
   await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   await page.waitForFunction(z=>qaPanel._mapRenderedView.zoom>z+.5,before.zoom);await ready();
   assert(await p.locator('.map-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth));
   await p.locator('.map-dialog').screenshot({path:`/tmp/navigation120-${index}-mobile.png`});
   const remembered=await page.evaluate(()=>({...qaPanel._mapView}));await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>qaPanel._mapNavigationTimer),null);
   assert.equal(await page.evaluate(()=>qaPanel._mapNavigationCleanup),null);
   await page.setViewportSize({width:1536,height:1100});
   await p.locator(`.map-buttons [data-map-index="${index}"]`).click();await ready();
   assert.equal(await page.evaluate(()=>qaPanel._mapView.x),remembered.x);
   assert.equal(await page.evaluate(()=>qaPanel._mapView.zoom),remembered.zoom);
   await p.locator('[data-action="map-reset-view"]').click();await page.waitForFunction(x=>qaPanel._mapRenderedView.x===x,initial.x);
   await page.keyboard.press('Escape');
  }
  assert.deepEqual(errors,[]);
  assert(await page.evaluate(()=>navCalls.filter(c=>c.viewport).length>=10));
  console.log('Navigation passed for lightning and animated radar: labels/default target, zoom buttons/wheel, real viewport forwarding, drag, touch pinch, refresh preserves view and animation, reset, close/reopen cleanup, mobile layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
