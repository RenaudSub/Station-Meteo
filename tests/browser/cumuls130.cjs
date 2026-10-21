const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const bundled=(await import('/tmp/weather-browser/node_modules/@sparticuz/chromium/build/index.js')).default;
 const browser=await chromium.launch({headless:true,executablePath:'/tmp/weather-chrome-assets/chromium',args:bundled.args});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720},hasTouch:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.qaPanel?._ready&&qaPanel.fc.hourly?.length);
  await page.evaluate(async()=>{
   const {boundedMapView}=await import('/station_meteo/frontend/map-navigation.js');
   const q=qaPanel,original=q.hass.callWS;window.cumulCalls=[];
   q.hass.callWS=async m=>{
    if(m.type!=='station_meteo/meteociel')return original(m);
    cumulCalls.push(m);const lightning=m.index===0,maximum=lightning?6:4,url=new URL(q.cfg.map_buttons[m.index].url);
    const initial={x:Number(url.searchParams.get('x')),y:Number(url.searchParams.get('y')),zoom:Number(url.searchParams.get('zoom'))};
    const v=m.viewport||initial,viewport=boundedMapView({maximum,kind:lightning?'lightning':'radar'},v.x,v.y,v.zoom),product=m.product||0;
    const tile='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768"><rect width="768" height="768" fill="#e2e8ed"/><path d="M160 200 Q550 100 440 630" fill="none" stroke="#04aaff" stroke-width="80"/></svg>');
    return {kind:viewport.kind,viewport,duration:30,product,unit:product?'mm':'mm/h',credit:'Météociel — données Météo-France',backgrounds:[],labels:[],palette:[{color:'#04aaff',value:.2},{color:'#008811',value:10}],frames:Array.from({length:lightning?1:product===15?28:12},(_,i)=>({time:new Date(Date.now()+(i-11)*300000).toISOString(),forecast:product===15&&i>=12,tiles:[{url:tile,rect:[0,0,768,768]}],points:[]}))};
   };
  });
  const p=page.locator('station-meteo-panel');
  assert.equal(await p.locator('.map-buttons [data-map-index="7"]').innerText(),'Cumuls');
  const open=async index=>{await p.locator(`.map-buttons [data-map-index="${index}"]`).click();await p.locator('canvas.native-weather-map').waitFor();await p.locator('[data-action="map-zoom-out"]:enabled').waitFor();};
  const assertVisiblePlayback=async()=>{
   const fit=await p.locator('.map-dialog').evaluate(d=>{const controls=d.querySelector('.sat-controls'),footer=d.querySelector('.map-footer'),r=controls.getBoundingClientRect(),f=footer.getBoundingClientRect();return {right:d.scrollWidth<=d.clientWidth,controlsBottom:r.bottom,footerBottom:f.bottom,screen:innerHeight};});
   assert(fit.right,JSON.stringify(fit));assert(fit.controlsBottom<=fit.screen,JSON.stringify(fit));assert(fit.footerBottom<=fit.screen,JSON.stringify(fit));
  };
  for(const index of [0,6,7]){
   await open(index);
   assert.equal(await p.locator('.map-navigation small').count(),0);
   assert.equal(await p.locator('.map-body > .map-navigation').count(),0);
   assert.equal(await p.locator('.map-layer-controls .map-navigation').count(),1);
   const fields=await p.locator('.map-layer-controls fieldset').all(),nav=await p.locator('.map-navigation').boundingBox(),rightField=await fields[1].boundingBox();
   assert(nav.x>=rightField.x+rightField.width-1);
   assert(nav.y>=rightField.y&&nav.y<rightField.y+rightField.height);
   if(index!==0){await assertVisiblePlayback();assert(await page.evaluate(()=>!!qaPanel._satTimer));}
   if(index===7){
    assert.equal(await p.locator('.dialog-head [data-radar-product] option').count(),8);
    assert.equal(await p.locator('[data-radar-product]').inputValue(),'1');
    for(const product of [5,15,1,3,2,6,7,4]){
     await p.locator('[data-radar-product]').selectOption(String(product));
     await page.waitForFunction(n=>qaPanel._mapData.product===n,product);
     await p.locator('canvas.native-weather-map').waitFor();
     assert.equal(await p.locator('.map-legend > span').innerText(),'mm');
     assert.equal(await page.evaluate(()=>cumulCalls.at(-1).product),product);
     assert.equal(new URL(await p.locator('.map-source').getAttribute('href')).searchParams.get('lame'),String(product));
    }
    await p.locator('[data-radar-product]').selectOption('15');await page.waitForFunction(()=>qaPanel._mapData.product===15);
    await p.locator('[data-sat-frame]').evaluate(el=>{el.value='20';el.dispatchEvent(new Event('change',{bubbles:true}));});
    assert.match(await p.locator('.map-timestamp').innerText(),/^Prévision du/);
    assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
    await p.locator('[data-action="map-zoom-out"]').click();await page.waitForFunction(()=>qaPanel._mapRenderedView.zoom===2);
    assert.equal(await page.evaluate(()=>cumulCalls.at(-1).product),15);
    assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
    await p.locator('[data-action="sat-play"]').click();await assertVisiblePlayback();
    await p.locator('.map-dialog').screenshot({path:'/tmp/cumuls130-desktop.png'});
   }
   await page.keyboard.press('Escape');
  }
  for(const viewport of [{width:1024,height:768},{width:800,height:600},{width:390,height:844}]){
   await page.setViewportSize(viewport);await open(7);await assertVisiblePlayback();
   assert(await p.locator('.map-dialog').evaluate(d=>d.scrollWidth<=d.clientWidth));
   await p.locator('.map-dialog').screenshot({path:`/tmp/cumuls130-${viewport.width}.png`});
   await page.keyboard.press('Escape');
  }
  await p.locator('[data-action="settings"]').click();await p.locator('[data-action="personalization"]').click();
  assert.equal(await p.locator('[data-map-index="7"][data-map-field="url"]').inputValue(),'https://www.meteociel.fr/observations-meteo/radarzoom.php?x=5764.4&y=9054.2&ech=3&zoom=2.5&lame=1');
  await p.locator('[data-map-index="7"][data-map-field="enabled"]').uncheck();await p.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.draft);
  assert.equal(await p.locator('.map-buttons [data-map-index="7"]').count(),0);
  assert.deepEqual(errors,[]);
  console.log('V1.3.0 passed: eight cumulative products, header selector, mm legend, forecast timestamps, autoplay/pause/navigation, compact controls on same row, playback/footer visible at 1280x720, 1024x768, 800x600 and 390x844, customization.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
