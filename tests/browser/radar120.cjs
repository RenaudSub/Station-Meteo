const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const bundled=(await import('/tmp/weather-browser/node_modules/@sparticuz/chromium/build/index.js')).default;
 const browser=await chromium.launch({headless:true,executablePath:'/tmp/weather-chrome-assets/chromium',args:bundled.args});
 try{
  const page=await browser.newPage({viewport:{width:1536,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765');
  await page.waitForFunction(()=>window.qaPanel?._ready&&qaPanel.fc.hourly?.length);
  await page.evaluate(async()=>{
   const q=qaPanel,original=q.hass.callWS;
   const old=structuredClone(q.cfg);old.map_buttons=old.map_buttons.slice(0,6);
   old.map_buttons[1].name='Mon radar';old.map_buttons[1].enabled=false;
   for(let i=1;i<=5;i++)old.map_buttons.push({...old.map_buttons[0],id:'custom'+i,name:'Carte '+i,mode:'iframe',url:'https://example.org/'+i});
   let migration=true;window.radarCalls=[];window.radarPartial=false;window.radarFail=false;
   q.hass.callWS=async m=>{
    if(m.type==='station_meteo/config'&&migration){migration=false;return structuredClone(old);}
    if(m.type==='station_meteo/meteociel'){
     radarCalls.push(m);if(radarFail)return {frames:[],reason:'http_503'};
     const image='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768"><rect width="768" height="768" fill="#cbdfe8"/><circle cx="320" cy="350" r="120" fill="#218ac0"/></svg>');
     return {kind:'radar',backgrounds:[],labels:[{name:'Perpignan',x:400,y:530}],palette:[{color:'#218ac0',value:1}],credit:'Météociel — données Météo-France',frames:Array.from({length:12},(_,i)=>({time:new Date(Date.now()-(11-i)*300000).toISOString(),tiles:[{url:radarPartial&&i===5?'/missing-tile.png':image,rect:[0,0,768,768]}]}))};
    }
    return original(m);
   };
   await q.init();
  });
  const p=page.locator('station-meteo-panel');
  assert.deepEqual(await page.evaluate(()=>qaPanel.cfg.map_buttons.slice(8).map(c=>c.id)),['custom1','custom2','custom3','custom4','custom5']);
  assert.equal(await page.evaluate(()=>qaPanel.cfg.map_buttons[1].name),'Mon radar');
  assert.equal(await p.locator('.map-buttons button[data-map-index="1"]').count(),0);
  const open=async()=>{await p.locator('.map-buttons button[data-map-index="6"]').click();await p.locator('canvas.native-weather-map').waitFor();};
  await open();
  assert.equal(await p.locator('#map-title').innerText(),'Précipitations');
  assert.equal(await p.locator('[data-lightning-option]').count(),0);
  assert.equal(await p.locator('[data-radar-option="cities"]').count(),4);
  assert.equal(await p.locator('[data-radar-option]').count(),7);
  assert.deepEqual(await page.evaluate(()=>radarCalls.at(-1).options),{cities:3,roads:true,rivers:true,relief:true});
  assert.equal(await page.evaluate(()=>qaPanel._satFrames.length),12);
  assert(await page.evaluate(()=>!!qaPanel._satTimer));
  await page.waitForFunction(()=>qaPanel._satIndex>0);
  assert.match(await p.locator('.map-timestamp').innerText(),/\d{2}h\d{2}/);
  await p.locator('[data-action="sat-play"]').click();
  assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
  await p.locator('[data-radar-option="cities"][value="0"]').check();
  await page.waitForFunction(()=>radarCalls.at(-1).options.cities===0);
  await p.locator('canvas.native-weather-map').waitFor();
  assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
  await p.locator('[data-radar-option="relief"]').uncheck();
  await page.waitForFunction(()=>radarCalls.at(-1).options.relief===false);
  await p.locator('canvas.native-weather-map').waitFor();
  await p.locator('[data-action="sat-play"]').click();
  await p.locator('[data-action="map-refresh"]').click();
  await p.locator('canvas.native-weather-map').waitFor();
  assert(await page.evaluate(()=>!!qaPanel._satTimer));
  await p.locator('[data-sat-frame]').evaluate(el=>{el.value='3';el.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(await page.evaluate(()=>qaPanel._satIndex),3);
  assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
  await p.locator('.map-dialog').screenshot({path:'/tmp/radar120-desktop.png'});
  await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>qaPanel._satTimer),null);
  await page.setViewportSize({width:390,height:1000});
  await open();
  assert(await p.locator('[data-radar-option="cities"][value="0"]').isChecked());
  assert(!await p.locator('[data-radar-option="relief"]').isChecked());
  assert(await page.evaluate(()=>!!qaPanel._satTimer));
  assert(await p.locator('.map-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth));
  await p.locator('.map-dialog').screenshot({path:'/tmp/radar120-mobile.png'});
  await page.evaluate(()=>radarPartial=true);await p.locator('[data-action="map-refresh"]').click();
  await page.waitForFunction(()=>qaPanel._satFrames.length===11);
  assert.match(await p.locator('.satellite-status').innerText(),/images.*indisponibles/i);
  await page.evaluate(()=>{radarPartial=false;radarFail=true;});await p.locator('[data-action="map-refresh"]').click();
  await page.waitForFunction(()=>!qaPanel._satTimer);
  await page.waitForFunction(()=>qaPanel.shadowRoot.querySelector('.satellite-status').textContent.includes('503'));
  await page.evaluate(()=>radarFail=false);await p.locator('[data-action="map-refresh"]').click();await p.locator('canvas.native-weather-map').waitFor();
  await page.keyboard.press('Escape');
  await p.locator('[data-action="settings"]').click();await p.locator('[data-action="personalization"]').click();
  assert(await p.locator('[data-action="add-map"]').isDisabled());
  assert.equal(await p.locator('[data-action="remove-map"]').count(),5);
  await p.locator('[data-map-index="6"][data-map-field="name"]').fill('Mon animation');
  await p.locator('[data-map-index="6"][data-map-field="enabled"]').uncheck();
  await p.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.draft);
  assert.equal(await p.locator('.map-buttons button[data-map-index="6"]').count(),0);
  await page.evaluate(()=>qaPanel.init());
  assert.equal(await page.evaluate(()=>qaPanel.cfg.map_buttons.length),13);
  assert.equal(await page.evaluate(()=>qaPanel.cfg.map_buttons[6].name),'Mon animation');
  assert.deepEqual(errors,[]);
  console.log('Radar passed: migration preserves five custom maps, automatic playback, pause/seek/refresh, cities/layers saved per button, timestamp, partial/error recovery, desktop/mobile, customizable built-in.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
