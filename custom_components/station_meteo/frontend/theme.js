/* Scheduled themes use the station's Home Assistant time zone. */
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function themeIsDark(config={},haDark=false,now=Date.now(),zone='UTC'){
 if(config.theme==='dark')return true;
 if(config.theme==='auto')return !!haDark;
 if(config.theme!=='schedule')return false;
 const valid=v=>/^([01]\d|2[0-3]):[0-5]\d$/.test(v||'');
 const start=valid(config.theme_dark_start)?config.theme_dark_start:'20:00',end=valid(config.theme_dark_end)?config.theme_dark_end:'08:00';
 if(start===end)return false;
 let parts;try{parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now);}catch{return false;}
 const time=parts.find(p=>p.type==='hour').value+':'+parts.find(p=>p.type==='minute').value;
 return start<end?time>=start&&time<end:time>=start||time<end;
}
export const themeMethods={
 applyTheme(){const config=this.draft||this.cfg||{};this.classList.toggle('sm-dark',themeIsDark(config,this._hass?.themes?.darkMode,Date.now(),this._hass?.config?.time_zone||'UTC'));},
 startThemeClock(){this.stopThemeClock();this._themeTimer=setInterval(()=>this.applyTheme(),15000);this._themeVisibility=()=>this.applyTheme();document.addEventListener('visibilitychange',this._themeVisibility);this.applyTheme();},
 stopThemeClock(){clearInterval(this._themeTimer);this._themeTimer=null;if(this._themeVisibility)document.removeEventListener('visibilitychange',this._themeVisibility);this._themeVisibility=null;},
 themeSettings(){const c=this.draft;return `<section class="theme-settings"><h3>${esc(this.t('theme'))}</h3><div class="settings-grid"><label>${esc(this.t('theme_mode'))}<select data-setting="theme">${['light','dark','auto','schedule'].map(mode=>`<option value="${mode}" ${(c.theme||'light')===mode?'selected':''}>${esc(this.t('theme_'+mode))}</option>`).join('')}</select></label>${c.theme==='schedule'?`<label>${esc(this.t('theme_dark_start'))}<input type="time" data-setting="theme_dark_start" value="${esc(c.theme_dark_start||'20:00')}"></label><label>${esc(this.t('theme_dark_end'))}<input type="time" data-setting="theme_dark_end" value="${esc(c.theme_dark_end||'08:00')}"></label>`:''}</div><p class="help">${esc(this.t('theme_schedule_help'))} ${esc(this.hass?.config?.time_zone||'UTC')}</p></section>`;},
};
