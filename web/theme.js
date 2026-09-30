(() => {
  'use strict';
  const key='plup-theme';
  const toggle=document.getElementById('theme-toggle');
  const current=()=>document.documentElement.dataset.theme==='dark'?'dark':'light';
  function apply(theme){
    const dark=theme==='dark';
    document.documentElement.dataset.theme=dark?'dark':'light';
    document.querySelector('meta[name="theme-color"]').content=dark?'#071522':'#f5f8fc';
    toggle.setAttribute('aria-pressed',String(dark));
    toggle.setAttribute('aria-label',dark?'Activează modul luminos':'Activează modul întunecat');
    toggle.querySelector('span').textContent=dark?'Light mode':'Dark mode';
    try{localStorage.setItem(key,dark?'dark':'light');}catch{}
  }
  let initial='light';
  try{initial=localStorage.getItem(key)==='dark'?'dark':'light';}catch{}
  apply(initial);
  toggle.addEventListener('click',()=>apply(current()==='dark'?'light':'dark'));
  window.PLUPTheme={current};
})();
