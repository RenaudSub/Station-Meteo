/* Viewport navigation loads neighbouring source tiles, rather than enlarging a screenshot. */
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function boundedMapView(base,x,y,zoom){
 zoom=Math.max(0,Math.min(base.maximum,zoom));
 const scale=2**(zoom-base.maximum),extent=768*2**base.maximum;
 const left=Math.max(0,Math.min(x-384,extent-768/scale));
 const top=Math.max(0,Math.min(y-384,extent-768/scale));
 return {...base,x:left+384,y:top+384,left,top,zoom,scale};
}
export const mapNavigationMethods={
 isNavigableMap(card){return this.isLightningCard(card)||this.isRadarCard(card);},
 mapNavigationControls(){return `<div class="map-navigation" role="group" aria-label="${esc(this.t('map_reset_view'))}"><button type="button" data-action="map-zoom-in" title="${esc(this.t('map_zoom_in'))}" aria-label="${esc(this.t('map_zoom_in'))}" disabled>+</button><button type="button" data-action="map-zoom-out" title="${esc(this.t('map_zoom_out'))}" aria-label="${esc(this.t('map_zoom_out'))}" disabled>−</button><button type="button" data-action="map-reset-view" disabled>${esc(this.t('map_reset_view'))}</button></div>`;},
 fitMapStage(dialog,ratio){const body=dialog.querySelector('.map-body'),stage=body.querySelector('.satellite-stage'),style=getComputedStyle(body);let occupied=dialog.querySelector('.dialog-head').getBoundingClientRect().height+parseFloat(style.paddingTop)+parseFloat(style.paddingBottom)+4;for(const child of body.children){if(child===stage||getComputedStyle(child).display==='none')continue;const css=getComputedStyle(child);occupied+=child.getBoundingClientRect().height+parseFloat(css.marginTop)+parseFloat(css.marginBottom);}const available=Math.max(160,window.innerHeight*.94-occupied);stage.style.width=Math.min(body.clientWidth,window.innerHeight*.65*ratio,available*ratio)+'px';},
 mapNavigationBusy(dialog,busy){for(const button of dialog.querySelectorAll('.map-navigation button'))button.disabled=busy||!this._mapView;},
 previewMapView(view){const old=this._mapRenderedView;if(!old)return;const canvas=this.shadowRoot.querySelector('.map-dialog .native-weather-map');if(canvas)canvas.style.transform=`translate(${(old.left-view.left)*view.scale/768*100}%,${(old.top-view.top)*view.scale/768*100}%) scale(${view.scale/old.scale})`;},
 setMapView(view){this._mapView=view;this._mapViewport={x:view.x,y:view.y,zoom:view.zoom};this.previewMapView(view);},
 queueMapView(view){if(!this._mapView)return;if(this.isLightningCard(this.cfg.map_buttons[this._mapCardIndex])){this._lightningSeen=null;this.stopLightningSound();}this._mapNavigationResume=!!(this._mapNavigationResume||this._satTimer);this.stopSatellite();this.setMapView(view);clearTimeout(this._mapNavigationTimer);this._mapNavigationTimer=setTimeout(()=>{this._mapNavigationTimer=null;this._radarAutoplay=!!this._mapNavigationResume;this._mapNavigationResume=false;this.reloadMap();},220);},
 zoomMap(delta,point={x:384,y:384}){const base=this._mapView;if(!base)return;const zoom=Math.max(0,Math.min(base.maximum,base.zoom+delta));if(Math.abs(zoom-base.zoom)<.0001)return;const scale=2**(zoom-base.maximum);this.queueMapView(boundedMapView(base,base.left+point.x/base.scale-point.x/scale+384,base.top+point.y/base.scale-point.y/scale+384,zoom));},
 resetMapView(){if(this._mapInitialView)this.queueMapView({...this._mapInitialView});},
 cancelMapNavigationLoad(){clearTimeout(this._mapNavigationTimer);this._mapNavigationTimer=null;},
 stopMapNavigation(){this.cancelMapNavigationLoad();this._mapNavigationCleanup?.();this._mapNavigationCleanup=null;this._mapPointers=null;this._mapNavigationResume=false;},
 bindMapNavigation(dialog){
  const controls=dialog.querySelector('.lightning-controls'),navigation=dialog.querySelector('.map-navigation');if(controls&&navigation){const row=document.createElement('div');row.className='map-layer-controls';for(const field of controls.querySelectorAll('fieldset'))row.append(field);row.append(navigation);controls.append(row);}const stage=dialog.querySelector('.satellite-stage'),pointers=new Map(),listeners=[];this._mapPointers=pointers;stage.classList.add('navigable-map');
  const listen=(type,handler,options)=>{stage.addEventListener(type,handler,options);listeners.push(()=>stage.removeEventListener(type,handler,options));};
  const point=e=>{const rect=stage.getBoundingClientRect();return {x:(e.clientX-rect.left)*768/rect.width,y:(e.clientY-rect.top)*768/rect.height};};
  const center=()=>{const list=[...pointers.values()];return list.length>1?{x:(list[0].x+list[1].x)/2,y:(list[0].y+list[1].y)/2}:list[0];};
  const distance=()=>{const list=[...pointers.values()];return list.length>1?Math.hypot(list[0].x-list[1].x,list[0].y-list[1].y):0;};
  let base,start,span,changed=false;
  const rebase=()=>{base=this._mapView;start=center();span=distance();};
  listen('wheel',e=>{if(!this._mapView||!stage.querySelector('canvas')||pointers.size)return;e.preventDefault();this.zoomMap(e.deltaY<0?.5:-.5,point(e));},{passive:false});
  listen('dblclick',e=>{if(!stage.querySelector('canvas'))return;e.preventDefault();this.zoomMap(.5,point(e));});
  listen('pointerdown',e=>{
   if(!this._mapView||!stage.querySelector('canvas')||(e.pointerType==='mouse'&&e.button!==0))return;
   e.preventDefault();if(!pointers.size){changed=false;this.cancelMapNavigationLoad();this._mapNavigationResume=!!(this._mapNavigationResume||this._satTimer);this.stopSatellite();clearTimeout(this._lightningPoll);this._lightningPoll=null;}
   pointers.set(e.pointerId,point(e));stage.setPointerCapture(e.pointerId);stage.classList.add('dragging');rebase();
  });
  listen('pointermove',e=>{
   if(!pointers.has(e.pointerId))return;e.preventDefault();pointers.set(e.pointerId,point(e));const at=center(),dist=distance();
   const zoom=Math.max(0,Math.min(base.maximum,base.zoom+(span>0&&dist>0?Math.log2(dist/span):0))),scale=2**(zoom-base.maximum);
   if(Math.hypot(at.x-start.x,at.y-start.y)<3&&Math.abs(zoom-base.zoom)<.005)return;
   changed=true;this.setMapView(boundedMapView(base,base.left+start.x/base.scale-at.x/scale+384,base.top+start.y/base.scale-at.y/scale+384,zoom));
  });
  const end=e=>{
   if(!pointers.has(e.pointerId))return;pointers.delete(e.pointerId);if(stage.hasPointerCapture(e.pointerId))stage.releasePointerCapture(e.pointerId);
   if(pointers.size){rebase();return;}stage.classList.remove('dragging');
   if(changed)this.queueMapView(this._mapView);else{if(this._mapNavigationResume&&this._satFrames?.length>1)this.toggleSatellite();this._mapNavigationResume=false;if(this.isLightningCard(this.cfg.map_buttons[this._mapCardIndex]))this._lightningPoll=setTimeout(()=>this.reloadMap(),30000);}
  };
  listen('pointerup',end);listen('pointercancel',end);
  const resize=()=>{if(this._satFrames?.length)this.showSatelliteFrame(this._satIndex);};window.addEventListener('resize',resize);listeners.push(()=>window.removeEventListener('resize',resize));this._mapNavigationCleanup=()=>{for(const remove of listeners)remove();pointers.clear();stage.classList.remove('dragging');};
 },
};
