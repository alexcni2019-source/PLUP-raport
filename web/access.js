/* UI follows server permissions; every API independently enforces them. */
(() => {
 'use strict';
 let profile;
 try{profile=JSON.parse(document.querySelector('meta[name=plup-access]')?.content||'null');}catch{}
 if(!profile)return;
 const modes=['weekday','weekend','plan','forecast'];
 window.PLUPAccess={...profile,can(mode,write=false){return this.modules.includes(mode)&&(!write||this.role!=='viewer');}};
 try{const previous=localStorage.getItem('plup-last-user')||'owner';if(previous!==profile.id){for(const key of Object.keys(localStorage))if(key.startsWith('plup-draft-'))localStorage.removeItem(key);}localStorage.setItem('plup-last-user',profile.id);}catch{}
 const access=window.PLUPAccess;
 const editableIds=['save-report-button','save-plan','forecast-save','reset-button','add-al','add-cu','forecast-add-al','forecast-add-cu','undo-plan-row','undo-forecast-row'];
 function apply(){
  document.documentElement.dataset.role=access.role;
  document.querySelectorAll('[data-view]').forEach(node=>{const mode=node.dataset.view;if(modes.includes(mode))node.hidden=!access.can(mode);});
  document.querySelectorAll('#data-backup-file').forEach(node=>{node.closest('section').hidden=access.role!=='owner';});
  if(access.role!=='viewer')return;
  for(const id of editableIds){const node=document.getElementById(id);if(node)node.hidden=true;}
  document.querySelectorAll('#report-view input,#report-view select,#report-view textarea,#plan-view input,#plan-view select,#plan-view textarea,#forecast-view input,#forecast-view select,#forecast-view textarea').forEach(node=>{
   if(!['plan-search','forecast-search','plan-material','forecast-material'].includes(node.id))node.disabled=true;
  });
  document.querySelectorAll('[data-remove],[data-stock-add],[data-restore-version],[data-stock-action=table],#inventory-import,#inventory-remove,#remaining-edit-button').forEach(node=>node.hidden=true);
  document.querySelectorAll('.smart-excel,.plan-import,.plan-paste-zone').forEach(node=>{node.hidden=true;const disclosure=node.closest('.workspace-disclosure');if(disclosure)disclosure.hidden=true;});
  document.querySelectorAll('[id^=smart-draft-]').forEach(node=>{const text='Mod de citire · rapoartele pot fi consultate și exportate.';if(node.textContent!==text)node.textContent=text;});
  document.querySelectorAll('.source-table-editor button').forEach(node=>node.hidden=true);
  document.querySelectorAll('.source-table-editor [contenteditable]').forEach(node=>node.contentEditable='false');
 }
 document.addEventListener('DOMContentLoaded',()=>{
  apply();
  new MutationObserver(apply).observe(document.getElementById('plup-modern-root')||document.body,{childList:true,subtree:true});
  const original=window.PLUPDashboard.show;
  window.PLUPDashboard.show=(mode,...args)=>{if(modes.includes(mode)&&!access.can(mode))return;original(mode,...args);};
  document.addEventListener('plup:access',apply);
 });
})();
