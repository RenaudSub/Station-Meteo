const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1536,height:1024}});page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8765');await page.waitForFunction(()=>window.qaPanel?._ready&&window.qaPanel?.fc?.daily?.length);await page.waitForFunction(()=>[...qaPanel.shadowRoot.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0));
for(const [w,h]of [[1536,1024],[820,1180],[390,844]]){await page.setViewportSize({width:w,height:h});await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>qaPanel.shadowRoot.querySelector('main').scrollWidth<=qaPanel.clientWidth),true,`overflow at ${w}`);}
await page.locator('station-meteo-panel').getByRole('button',{name:'Configuration de la station'}).click();await page.locator('station-meteo-panel').getByRole('button',{name:'Autoconfig'}).click();assert.match(await page.locator('station-meteo-panel').locator('.auto-result').innerText(),/entités associées/);const root=page.locator('station-meteo-panel');await root.locator('[data-setting="location"]').fill('Test <script>alert(1)</script>');await root.locator('[data-setting="location"]').dispatchEvent('change');await root.locator('[data-setting="language"]').selectOption('en');await root.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.waitForFunction(()=>qaPanel.dict.title==='Weather station'&&!qaPanel.dialogOpen);assert.match(await root.locator('h1').innerText(),/Weather station/);assert.equal(await root.locator('.place strong').innerText(),'Test <script>alert(1)</script>');assert.equal(await root.locator('script').count(),0);
for(const lang of ['es','fr']){await root.locator('.gear').click();await root.locator('[data-setting="language"]').selectOption(lang);await root.locator('[data-action="save"]').click();await page.waitForFunction(l=>qaPanel.lang()===l&&!qaPanel.dialogOpen,lang);}
// Cancel is non-mutating and the dialog has no horizontal overflow.
await root.locator('.gear').click();assert.equal(await page.evaluate(()=>{const d=qaPanel.shadowRoot.querySelector('dialog');return d.scrollWidth<=d.clientWidth}),true);await root.locator('[data-setting="location"]').fill('Unsaved');await root.locator('[data-setting="location"]').dispatchEvent('change');await root.locator('[data-action="cancel"]').last().click();assert.equal(await root.locator('.place strong').innerText(),'Test <script>alert(1)</script>');
await page.evaluate(()=>{qaPanel.cfg.location='Casefabre';qaPanel.render();});
// Filters use semantic metadata and exclude even renamed AdGuard entities.
await page.setViewportSize({width:1536,height:1024});await root.locator('.gear').click();
assert.equal(await root.locator('datalist option[value="sensor.adguard_queries"]').count(),0);
assert.equal(await root.locator('datalist option[value="sensor.dns_queries"]').count(),0);
await root.locator('[data-local="orientation"]').fill('155');await root.locator('[data-local="orientation"]').dispatchEvent('change');
await root.locator('[data-action="notifications"]').click();
assert.equal(await root.locator('[data-notification="enabled"]').isChecked(),false);
await root.locator('[data-notification="enabled"]').check();await root.locator('[data-recipient="notify.mobile_app_test"]').check();

await root.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.dialogOpen);
assert.equal(await page.evaluate(()=>qaPanel.orientation()),155);
assert.match(await root.locator('.heading-note').innerText(),/155/);
assert.equal(await page.evaluate(()=>qaPanel.cfg.notifications.enabled),true);
assert.deepEqual(await page.evaluate(()=>qaPanel.cfg.notifications.recipients),['notify.mobile_app_test']);
assert.match(await root.locator('.compass').innerHTML(),/rotate\(178 110 110\)/); // wind 153° minus heading 155°
// Rotate labels without rotating their text, and preserve the raw wind direction.
assert.equal(await page.evaluate(()=>qaPanel.value('wind_direction')),153);
await root.locator('.gear').click();await root.locator('[data-local="orientation"]').fill('0');await root.locator('[data-local="orientation"]').dispatchEvent('change');await root.locator('[data-action="cancel"]').last().click();assert.equal(await page.evaluate(()=>qaPanel.orientation()),155);
// Full names and proper French prepositions; the compass alone keeps abbreviations.
assert.deepEqual(await page.evaluate(()=>[0,45,90,135,180,225,270,315].map(d=>qaPanel.windPhrase(d))),['Vent du Nord','Vent du Nord-Est','Vent d’Est','Vent du Sud-Est','Vent du Sud','Vent du Sud-Ouest','Vent d’Ouest','Vent du Nord-Ouest']);
assert.match(await root.locator('.wind-direction').innerText(),/Vent du Sud-Est/);
// Recorder receives an explicit end time, including measurements just added today.
assert.equal(await page.evaluate(()=>qaHistoryPaths.every(path=>Date.parse(new URL('/api/'+path,location.origin).searchParams.get('end_time'))>Date.now()-60000)),true);
await page.evaluate(async()=>{window.qaRecentHistory=true;await qaPanel.fetchHistory();qaPanel.render();});
assert.deepEqual(await page.evaluate(()=>qaPanel.extrema()),{min:21,max:25});
assert.equal(await page.evaluate(()=>qaPanel.points('temperature').length),2);
await page.evaluate(()=>window.qaRecentHistory=false);
// Pressure analysis needs a three-hour baseline; the forecast supplies storm wording.
await page.evaluate(()=>{const now=Date.now();qaPanel.historyRaw={[qaPanel.cfg.entities.pressure]:[{t:now-10801000,v:992},{t:now-60000,v:987.8}]};qaPanel.render();});
assert.match(await root.locator('.bulletin p').innerText(),/forte baisse.*Dégradation possible/);
await page.evaluate(()=>{qaPanel.fc.hourly=[{datetime:new Date(Date.now()+3600000).toISOString(),condition:'lightning'}];qaPanel.render();});assert.match(await root.locator('.bulletin p').innerText(),/prévoit un orage/);
await page.setViewportSize({width:820,height:1180});await page.waitForTimeout(250);assert.match(await root.locator('.heading-note').innerText(),/155/);

await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);assert.equal(await root.locator('.heading-note').count(),0);assert.match(await root.locator('.compass').innerHTML(),/rotate\(333 110 110\)/);
await root.locator('.gear').click();assert.equal(await root.locator('[data-local="orientation"]').count(),0);await root.locator('[data-action="notifications"]').click();assert.equal(await page.evaluate(()=>{const d=qaPanel.shadowRoot.querySelector('dialog');return d.scrollWidth<=d.clientWidth}),true);await root.locator('[data-action="cancel"]').last().click();
// Unavailable source values never become zero.
await page.evaluate(()=>{qaStates[qaPanel.cfg.entities.temperature].state='unavailable';qaPanel.render();});assert.match(await root.locator('.hero-temp').innerText(),/—/);assert.match(await root.locator('.status').innerText(),/partiellement/);
// Browse transfers the file, then Save commits the returned image path.
await root.locator('.gear').click();
await root.locator('[data-upload]').setInputFiles({name:'maison.webp',mimeType:'image/webp',buffer:require('node:fs').readFileSync('custom_components/station_meteo/frontend/weather-icons/cloudy.webp')});
await page.waitForFunction(()=>qaPanel.draft?.background_url==='/station_meteo/images/test-cloud.webp'&&!qaPanel._uploading);
assert.match(await root.locator('.upload-status').innerText(),/Photo transférée/);
assert.equal(await root.locator('[data-setting="background_url"]').inputValue(),'/station_meteo/images/test-cloud.webp');
assert.equal(await page.evaluate(()=>qaPanel.cfg.background_url||''),''); // not yet applied
await root.locator('[data-action="cancel"]').last().click();
assert.equal(await page.evaluate(()=>qaPanel.cfg.background_url||''),'');
assert.ok(await page.evaluate(()=>qaUploaded.content.length>1000));
// Real photo and locally bundled 3D forecast icons; failing external/local photo falls back.
assert.equal(await root.locator('.hour-weather-image').count()>0,true);
assert.equal(await root.locator('.tomorrow-weather-image').count(),1);
assert.equal(await root.locator('.hero-photo').getAttribute('src'),'/station_meteo/frontend/landscape.svg');
await page.evaluate(()=>{qaPanel.cfg.background_url='/local/not-found.jpg';qaPanel.render();});
await page.waitForFunction(()=>qaPanel._failedBackground==='/local/not-found.jpg'&&qaPanel.shadowRoot.querySelector('.hero-photo').complete);
assert.equal(await root.locator('.photo-credit').count(),0);
assert.equal(await root.locator('.hero-photo').getAttribute('src'),'/station_meteo/frontend/landscape.svg');
// Permission boundary: normal users can see the panel but have no settings gear.
await page.evaluate(()=>{qaPanel.hass.user.is_admin=false;qaPanel.render();});assert.equal(await root.locator('.gear').count(),0);
await page.evaluate(()=>{qaPanel.hass.user.is_admin=true;qaPanel.render();});
await page.setViewportSize({width:820,height:1180});
await root.locator('.gear').click();
await root.locator('[data-action="personalization"]').click();
assert.equal(await root.locator('.icon-customization').count(),17);
await root.locator('[data-upload-icon="cloudy"]').setInputFiles({name:'cloud.webp',mimeType:'image/webp',buffer:require('node:fs').readFileSync('tests/browser/sample-cloud.webp')});
await page.waitForFunction(()=>qaPanel.draft?.weather_icons?.cloudy&&!qaPanel._uploading);
assert.equal(await root.locator('.custom-icon-preview').count(),1);

await root.locator('[data-action="save"]').click();
await page.waitForFunction(()=>!qaPanel.dialogOpen);
assert.match(await page.evaluate(()=>qaPanel.weatherImage('cloudy')),/test-cloud.webp/);

await root.locator('.gear').click();await root.locator('[data-action="personalization"]').click();
await root.locator('[data-action="reset-icon"][data-condition="cloudy"]').click();
assert.equal(await page.evaluate(()=>qaPanel.draft.weather_icons.cloudy),undefined);
await root.locator('[data-action="cancel"]').last().click();
assert.match(await page.evaluate(()=>qaPanel.weatherImage('cloudy')),/test-cloud.webp/);
await page.setViewportSize({width:390,height:844});
await root.locator('.gear').click();await root.locator('[data-action="personalization"]').click();
assert.equal(await page.evaluate(()=>{const d=qaPanel.shadowRoot.querySelector('dialog');return d.scrollWidth<=d.clientWidth}),true);
await root.locator('[data-action="reset-icon"][data-condition="cloudy"]').click();
await root.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.dialogOpen);
assert.match(await page.evaluate(()=>qaPanel.weatherImage('cloudy')),/src="[^"]*cloudy.webp"/);
// Météo-France supplies amounts, not probabilities. Missing values remain unknown.
await page.setViewportSize({width:1536,height:1024});
await page.evaluate(()=>{qaPanel.fc.hourly=Array.from({length:12},(_,i)=>({datetime:new Date(Date.now()+i*3600000).toISOString(),condition:i<4?'partlycloudy':'rainy',temperature:24-i*.6,precipitation_probability:i*7})).map((f,i)=>{const {precipitation_probability,...rest}=f;return {...rest,precipitation:i===2?null:i===0?0:i*.2};});qaPanel.render();});
assert.equal(await root.locator('.rain-zero').count(),1);
assert.ok(await root.locator('.rain-bar').count()>0);
assert.match(await root.locator('.legend').innerText(),/Pluie prévue mm/);
assert.match(await root.locator('.hour small').first().innerText(),/0,0 mm/);
assert.match(await root.locator('.hour small').nth(2).innerText(),/— mm/);

const smooth=await page.evaluate(()=>{const input=[{t:0,v:0},{t:60000,v:10},{t:120000,v:0}];return {before:input.map(p=>p.v),after:qaPanel.smoothPoints(input).map(p=>p.v),svg:qaPanel.sparkSvg(input,'blue',true)};});
assert.deepEqual(smooth.before,[0,10,0]);assert.deepEqual(smooth.after,[0,5,0]);assert.match(smooth.svg,/ C/);
// Provided compass and independent arrow follow heading and air movement.
await root.locator('.gear').click();await root.locator('[data-action="personalization"]').click();
await root.locator('[data-compass-select="compass"]').selectOption('/station_meteo/frontend/compass-assets/rose-3d.webp');
await root.locator('[data-compass-select="arrow"]').selectOption('/station_meteo/frontend/compass-assets/arrow-modern.svg');

await root.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.dialogOpen);
assert.match(await root.locator('.compass').innerHTML(),/rotate\(25 110 110\)/);
assert.match(await root.locator('.compass').innerHTML(),/arrow-modern.svg/);
await page.evaluate(()=>{qaStates[qaPanel.cfg.entities.wind_direction].state='180';qaPanel.render();});
assert.match(await root.locator('.compass').innerHTML(),/rotate\(205 110 110\)/);
assert.match(await root.locator('.wind-direction').innerText(),/Vent du Sud/);

await root.locator('.gear').click();await root.locator('[data-action="personalization"]').click();
await root.locator('[data-upload-icon="arrow"]').setInputFiles({name:'arrow.svg',mimeType:'image/svg+xml',buffer:require('node:fs').readFileSync('custom_components/station_meteo/frontend/compass-assets/arrow-feathers.svg')});
await page.waitForFunction(()=>qaPanel.draft?.arrow_url==='/station_meteo/images/test-arrow.svg'&&!qaPanel._uploading);
await root.locator('[data-action="cancel"]').last().click();
assert.match(await page.evaluate(()=>qaPanel.cfg.arrow_url),/arrow-modern.svg/);
// Broken custom arrow and compass fall back independently.
await page.evaluate(()=>{qaPanel.cfg.arrow_url='/local/no-arrow.svg';qaPanel.cfg.compass_url='/local/no-compass.webp';qaPanel.render();});
await page.waitForFunction(()=>qaPanel._failedCompass?.arrow&&qaPanel._failedCompass?.compass,{},{timeout:10000});
assert.equal(await root.locator('.compass image').count(),0);
// Weather image DOM nodes survive live updates, preserving animation playback.
assert.equal(await page.evaluate(()=>{const before=qaPanel.shadowRoot.querySelector('.hero-weather-image');qaPanel.render();return before===qaPanel.shadowRoot.querySelector('.hero-weather-image');}),true);
await page.emulateMedia({reducedMotion:'reduce'});await page.evaluate(()=>qaPanel.render());
await page.waitForFunction(()=>qaPanel.shadowRoot.querySelector('.hour-weather-image').getAttribute('src').startsWith('data:image/png'));
await page.emulateMedia({reducedMotion:'no-preference'});
// All seven graphs open above the dashboard with matching paths and responsive width.
await page.emulateMedia({reducedMotion:'reduce'});
await page.evaluate(async()=>{window.qaRecentHistory=false;qaStates[qaPanel.cfg.entities.temperature].state='24.3';await qaPanel.fetchHistory();qaPanel.render();});
assert.equal(await root.locator('.graph-trigger').count(),7);
assert.equal(await root.locator('.tile-title h3').filter({hasText:'Précipitations'}).count(),1);
for(const role of ['wind_speed','temperature','rain_rate','humidity','uv','irradiance','pressure']){
 const small=await root.locator(`[data-graph-role="${role}"] .spark-line`).getAttribute('d').catch(()=>null);
 await root.locator(`[data-graph-role="${role}"]`).click();
 assert.equal(await root.locator('.graph-dialog').isVisible(),true);
 if(small)assert.equal(await root.locator('.graph-dialog .spark-line').getAttribute('d'),small);
 assert.equal(await page.evaluate(()=>{const d=qaPanel.shadowRoot.querySelector('.graph-dialog');return d.scrollWidth<=d.clientWidth}),true);
 await root.locator('[data-action="close-graph"]').click();
 assert.equal(await root.locator('.graph-dialog').count(),0);
}
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
await root.locator('[data-graph-role="temperature"]').click();
assert.equal(await page.evaluate(()=>{const d=qaPanel.shadowRoot.querySelector('.graph-dialog');return d.getBoundingClientRect().width<=390&&d.scrollWidth<=d.clientWidth}),true);
await page.keyboard.press('Escape');assert.equal(await root.locator('.graph-dialog').count(),0);
// The same viewer is available to non-admin users; fallback choice is retained by Save.
await page.evaluate(()=>{qaPanel.hass.user.is_admin=false;qaPanel.render();});await root.locator('[data-graph-role="pressure"]').click();await root.locator('[data-action="close-graph"]').click();
await page.evaluate(()=>{qaPanel.hass.user.is_admin=true;qaPanel.render();});await root.locator('.gear').click();
assert.ok(await root.locator('#list-weather_fallback option[value="weather.met_no"]').count());
await root.locator('[data-role="weather_fallback"]').fill('weather.met_no');await root.locator('[data-role="weather_fallback"]').dispatchEvent('change');await root.locator('[data-action="save"]').click();await page.waitForFunction(()=>!qaPanel.dialogOpen);
assert.equal(await page.evaluate(()=>qaPanel.cfg.entities.weather_fallback),'weather.met_no');
assert.ok(await root.locator('.forecast-attribution').count());
assert.deepEqual(errors,[]);console.log('PASS: responsive, FR/EN/ES, filtered entities, notifications settings, orientation persistence/155 degrees/mobile north, pressure bulletin, storm forecast, unavailable, permissions');await browser.close();})();
