(() => {
  'use strict';
  const key='plup-theme',toggle=document.getElementById('theme-toggle'),systemButton=document.getElementById('theme-system');
  const system=matchMedia('(prefers-color-scheme: dark)');
  let preference='system';
  try{const saved=localStorage.getItem(key);if(saved==='dark'||saved==='light')preference=saved;}catch{}
  const current=()=>document.documentElement.dataset.theme==='dark'?'dark':'light';
  function apply(){
    const dark=preference==='system'?system.matches:preference==='dark';
    document.documentElement.dataset.theme=dark?'dark':'light';
    document.querySelector('meta[name="theme-color"]').content=dark?'#10141c':'#f2f4f8';
    toggle.setAttribute('aria-pressed',String(dark));toggle.setAttribute('aria-label',dark?'Activează modul luminos':'Activează modul întunecat');
    toggle.querySelector('span').textContent=dark?'Mod luminos':'Mod întunecat';
    systemButton.setAttribute('aria-pressed',String(preference==='system'));systemButton.title=preference==='system'?'Aspectul urmărește setarea sistemului':'Folosește aspectul sistemului';
  }
  function set(value){preference=value;try{localStorage.setItem(key,value);}catch{}apply();}
  apply();toggle.addEventListener('click',()=>set(current()==='dark'?'light':'dark'));systemButton.addEventListener('click',()=>set('system'));
  system.addEventListener('change',()=>{if(preference==='system')apply();});
  window.PLUPTheme={current};
})();
