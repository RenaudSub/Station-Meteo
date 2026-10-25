/* Hide only this document's enclosing HA drawer while Station Météo is framed. */
const DRAWER_CSS=`
.sidebar-shell { display:none!important; }
.app-content { padding-inline-start:0!important; padding-left:0!important; padding-right:0!important; }
wa-drawer { display:none!important; }
::slotted(ha-sidebar) { display:none!important; }
`;
export const embedFrameMethods={
 embeddedStationActive(){
  if(!this.isConnected)return false;
  try{if(window.top===window.self)return false;}catch{return false;}
  const route=window.location.pathname.split('/').filter(Boolean)[0];
  const panel=this._hass?.panelUrl;
  return route==='station-meteo'&&(!panel||panel==='station-meteo');
 },
 enclosingHaDrawer(){
  // Follow the panel's own ancestors, crossing open shadow roots. Never search
  // another page, the parent frame, or an unrelated drawer in this document.
  let node=this;
  while(node){if(node.localName==='ha-drawer')return node;node=node.parentElement||node.getRootNode()?.host;}
  return null;
 },
 startEmbeddedChrome(){
  this.stopEmbeddedChrome();this._embedAttempts=0;
  this._embedRoute=()=>{this._embedAttempts=0;this.syncEmbeddedChrome();};
  for(const event of ['location-changed','popstate','hashchange'])window.addEventListener(event,this._embedRoute);
  this.syncEmbeddedChrome();
 },
 syncEmbeddedChrome(){
  clearTimeout(this._embedRetry);this._embedRetry=null;
  if(!this.embeddedStationActive()){this.releaseEmbeddedChrome();return;}
  const drawer=this.enclosingHaDrawer(),root=drawer?.shadowRoot;
  const modal=root?.querySelector('wa-drawer');
  const desktop=!!(root?.querySelector('.sidebar-shell')&&root.querySelector('.app-content'));
  // Do not hide an already-open modal drawer: its native modal state might
  // otherwise leave the page inert. Let HA close it normally, then apply.
  const supported=desktop||!!(modal&&root.querySelector('slot[name="appContent"]')&&!drawer.open&&!modal.open&&!modal.hasAttribute('open'));
  if(!root||!supported){
   this.releaseEmbeddedChrome();
   if(this._embedAttempts++<40)this._embedRetry=setTimeout(()=>this.syncEmbeddedChrome(),500);
   return;
  }
  if(this._embedRoot!==root){
   this.releaseEmbeddedChrome();this._embedRoot=root;
   this._embedObserver=new MutationObserver(()=>{if(!this._embedFrame)this._embedFrame=requestAnimationFrame(()=>{this._embedFrame=null;this.syncEmbeddedChrome();});});
   this._embedObserver.observe(root,{childList:true,subtree:true,attributes:true,attributeFilter:['open','type']});
  }
  if(!this._embedStyle?.isConnected){
   const style=document.createElement('style');style.dataset.stationMeteoEmbed='';style.textContent=DRAWER_CSS;root.append(style);this._embedStyle=style;
   if(!style.sheet){this.releaseEmbeddedChrome();return;}
  }
  this.classList.add('sm-embedded');
 },
 releaseEmbeddedChrome(){
  this._embedObserver?.disconnect();this._embedObserver=null;
  if(this._embedFrame)cancelAnimationFrame(this._embedFrame);this._embedFrame=null;
  this._embedStyle?.remove();this._embedStyle=null;this._embedRoot=null;
  this.classList.remove('sm-embedded');
 },
 stopEmbeddedChrome(){
  clearTimeout(this._embedRetry);this._embedRetry=null;
  if(this._embedRoute)for(const event of ['location-changed','popstate','hashchange'])window.removeEventListener(event,this._embedRoute);
  this._embedRoute=null;this.releaseEmbeddedChrome();
 },
};
