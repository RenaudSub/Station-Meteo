const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const bundled=(await import('/tmp/weather-browser/node_modules/@sparticuz/chromium/build/index.js')).default;
 const browser=await chromium.launch({headless:true,executablePath:'/tmp/weather-chrome-assets/chromium',args:bundled.args});
 try{
  const page=await browser.newPage({viewport:{width:1536,height:1000},hasTouch:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.qaNow=Date.parse('2026-10-25T19:00:00Z');Date.now=()=>qaNow;});
  await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.qaPanel?._ready&&qaPanel.fc.hourly?.length);
  const p=page.locator('station-meteo-panel');
  const initial=await p.evaluate(el=>({background:getComputedStyle(el).backgroundColor,color:getComputedStyle(el).color}));
  assert(!await p.evaluate(el=>el.classList.contains('sm-dark')));
  const settings=async()=>{await p.locator('[data-action="settings"]').click();await p.locator('[data-action="personalization"]').click();};
  await settings();assert.equal(await p.locator('[data-setting="theme"]').inputValue(),'light');
  await p.locator('[data-setting="theme"]').selectOption('dark');assert(await p.evaluate(el=>el.classList.contains('sm-dark')));
  await p.locator('.settings-dialog').screenshot({path:'/tmp/theme140-settings-dark.png'});
  await p.locator('[data-action="cancel"]').first().click();
  assert(!await p.evaluate(el=>el.classList.contains('sm-dark')));
  assert.deepEqual(await p.evaluate(el=>({background:getComputedStyle(el).backgroundColor,color:getComputedStyle(el).color})),initial);
  await settings();await p.locator('[data-setting="theme"]').selectOption('schedule');
  assert.equal(await p.locator('[data-setting="theme_dark_start"]').inputValue(),'20:00');
  assert.equal(await p.locator('[data-setting="theme_dark_end"]').inputValue(),'08:00');
  await p.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.draft);
  assert(await p.evaluate(el=>el.classList.contains('sm-dark')));
  await p.locator('main').screenshot({path:'/tmp/theme140-desktop-dark.png'});
  await page.evaluate(async()=>{
   const {boundedMapView}=await import('/station_meteo/frontend/map-navigation.js');
   const q=qaPanel,original=q.hass.callWS;window.viewCalls=[];
   q.hass.callWS=async m=>{
    if(m.type!=='station_meteo/meteociel')return original(m);
    viewCalls.push(m);const card=q.cfg.map_buttons[m.index],url=new URL(card.url),lightning=m.index===0,maximum=lightning?6:4;
    const initial={x:Number(url.searchParams.get('x')),y:Number(url.searchParams.get('y')),zoom:Number(url.searchParams.get('zoom'))};
    const v=m.viewport||initial,viewport=boundedMapView({maximum,kind:lightning?'lightning':'radar'},v.x,v.y,v.zoom);
    return {kind:viewport.kind,viewport,duration:30,product:m.product||0,unit:m.product?'mm':'mm/h',credit:'Météociel',backgrounds:[],labels:[],palette:[],frames:Array.from({length:lightning?1:3},(_,i)=>({time:new Date(Date.now()-(2-i)*300000).toISOString(),tiles:[],points:[]}))};
   };
  });
  const ready=async()=>{await p.locator('canvas.native-weather-map').waitFor();await p.locator('[data-action="map-zoom-out"]:enabled').waitFor();};
  const open=async index=>{await p.locator(`.map-buttons [data-map-index="${index}"]`).click();await ready();};
  for(const index of [0,6,7]){
   await open(index);const configured=await page.evaluate(()=>({...qaPanel._mapInitialView}));
   await p.locator('[data-action="map-zoom-out"]').click();await page.waitForFunction(z=>qaPanel._mapRenderedView.zoom<z,configured.zoom);await ready();
   const box=await p.locator('.navigable-map').boundingBox(),before=await page.evaluate(()=>qaPanel._mapView.x);
   await page.mouse.move(box.x+box.width*.4,box.y+box.height*.4);await page.mouse.down();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.45,{steps:5});await page.mouse.up();
   await page.waitForFunction(x=>Math.abs(qaPanel._mapRenderedView.x-x)>1,before);await ready();
   const remembered=await page.evaluate(()=>({...qaPanel._mapView}));
   await page.keyboard.press('Escape');await open(index);
   assert.equal(await page.evaluate(()=>qaPanel._mapView.x),remembered.x);assert.equal(await page.evaluate(()=>qaPanel._mapView.zoom),remembered.zoom);
   await page.keyboard.press('Escape');await page.evaluate(()=>qaPanel.init());await open(index);
   assert.equal(await page.evaluate(()=>qaPanel._mapView.y),remembered.y);
   assert.deepEqual(await page.evaluate(()=>viewCalls.at(-1).viewport),{x:remembered.x,y:remembered.y,zoom:remembered.zoom});
   await p.locator('[data-action="map-reset-view"]').click();await page.waitForFunction(x=>qaPanel._mapRenderedView.x===x,configured.x);await ready();
   assert.equal(await page.evaluate(()=>qaPanel._mapView.zoom),configured.zoom);
   await page.keyboard.press('Escape');
  }
  // A target URL change ignores the previous local viewport for that button.
  await page.evaluate(()=>{const c=qaPanel.cfg.map_buttons[6];const u=new URL(c.url);u.searchParams.set('x','5000');c.url=u.href;qaPanel.render();});
  await open(6);assert.equal(await page.evaluate(()=>qaPanel._mapView.x),5000);
  // The clock switches the existing dialog's theme without closing/rebuilding it.
  await page.evaluate(()=>{window.openDialog=qaPanel.shadowRoot.querySelector('.map-dialog');qaNow=Date.parse('2026-10-26T07:00:00Z');});
  await page.waitForFunction(()=>!qaPanel.classList.contains('sm-dark'),{},{timeout:20000});
  assert(await page.evaluate(()=>openDialog.isConnected&&openDialog.open));await page.keyboard.press('Escape');
  await page.evaluate(()=>{qaPanel.cfg.theme='auto';qaPanel.hass={...qaPanel.hass,themes:{darkMode:true}};});assert(await p.evaluate(el=>el.classList.contains('sm-dark')));
  await page.evaluate(()=>qaPanel.hass={...qaPanel.hass,themes:{darkMode:false}});assert(!await p.evaluate(el=>el.classList.contains('sm-dark')));
  await page.evaluate(()=>{qaPanel.cfg.theme='dark';qaPanel.applyTheme();});
  await page.setViewportSize({width:390,height:844});await p.locator('main').screenshot({path:'/tmp/theme140-mobile-dark.png'});
  await p.locator('[data-action="settings"]').click();await p.locator('[data-action="notifications"]').click();
  assert.equal(await p.locator('[data-notification="vigilance"]').count(),1);assert(!await p.locator('[data-notification="vigilance"]').isChecked());
  await p.locator('[data-notification="vigilance"]').check();await p.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.draft);
  assert(await page.evaluate(()=>qaPanel.cfg.notifications.vigilance));
  await page.evaluate(()=>qaPanel.init());assert(await page.evaluate(()=>qaPanel.cfg.notifications.vigilance));
  // Malformed storage cannot produce an invalid navigation request.
  await page.evaluate(()=>localStorage.setItem('station_meteo.map_view.lightning','{"url":"wrong","view":{"x":null,"y":0,"zoom":99}}'));
  await open(0);assert.equal(await page.evaluate(()=>qaPanel._mapView.zoom),5.9);await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);
  console.log('V1.4.0 preferences passed: default light unchanged, dark preview/cancel, schedule saving/clock boundary with dialog open, HA auto, three independent durable viewports and reset, URL change invalidation, mobile dark, vigilance option persistence.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
