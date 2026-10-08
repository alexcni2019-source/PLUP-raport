(() => {
  'use strict';
  const dirty=new Set();
  const controller=mode=>mode==='plan'?window.PLUPPlan:mode==='forecast'?window.PLUPForecast:window.PLUPReport;
  function modeFor(target){
    if(target.closest('#plan-view'))return 'plan';
    if(target.closest('#forecast-view'))return 'forecast';
    if(target.closest('#report-view'))return window.PLUPReport?.payload().mode;
  }
  document.addEventListener('input',event=>{if(event.target.matches('input[data-key],#report-date,#plan-date,#plan-week,#plan-incoming,#forecast-date')){const mode=modeFor(event.target);if(mode)dirty.add(mode);}});
  document.addEventListener('click',event=>{if(event.target.closest('[data-remove],#add-al,#add-cu,#forecast-add-al,#forecast-add-cu,#undo-plan-row,#undo-forecast-row')){const mode=modeFor(event.target);if(mode)dirty.add(mode);}},true);
  function markClean(mode,submitted){
    if(submitted&&JSON.stringify(controller(mode)?.payload())!==JSON.stringify(submitted))return;
    dirty.delete(mode);
  }
  window.PLUPUI={markClean,markDirty:mode=>dirty.add(mode),confirmReplace(mode){return !dirty.has(mode)||window.confirm('Ai modificări nesalvate în acest formular. Le înlocuiești cu un alt raport?');}};
  window.addEventListener('beforeunload',event=>{if(dirty.size){event.preventDefault();event.returnValue='';}});
  const observed=new WeakSet();
  function observeButtons(){
    document.querySelectorAll('button[data-busy-label]').forEach(button=>{
      if(observed.has(button))return;observed.add(button);
      let original='';
      new MutationObserver(()=>{
        button.setAttribute('aria-busy',String(button.disabled));
        if(button.disabled&&!original){original=button.innerHTML;button.textContent=button.dataset.busyLabel;}
        else if(!button.disabled&&original){button.innerHTML=original;original='';}
      }).observe(button,{attributes:true,attributeFilter:['disabled']});
    });
  }
  observeButtons();
})();
