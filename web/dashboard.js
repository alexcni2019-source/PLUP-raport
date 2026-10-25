(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  let csrf='',provider='password',currentView='dashboard',opening=false,viewRevision=0,historyOffset=0,historyRevision=0;
  const names={dashboard:'Centru de raportare PLUP',plan:'Plan de producție',weekday:'Raport zilnic',weekend:'Raport pentru 3 zile',forecast:'Previz zilnic',history:'Istoric rapoarte'};
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const versions=new Map();
  const scrollPositions=new Map();
  const motion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
  function loginGate(message=''){$('login-gate').hidden=false;$('login-loading').hidden=true;if(provider==='github'){$('login-form').hidden=true;let card=$('identity-renew');if(!card){card=document.createElement('div');card.id='identity-renew';card.className='login-card';card.innerHTML='<h2>Reconectare securizată</h2><p>Formularul rămâne în această fereastră. Conectează-te în fila nouă, apoi revino aici.</p><a class="primary-button" href="/auth/login" target="_blank" rel="noopener noreferrer">Continuă cu GitHub</a><button class="secondary-button" type="button">Am revenit · verifică accesul</button>';card.querySelector('button').addEventListener('click',checkAccess);$('login-gate').append(card);}card.hidden=false;card.querySelector('a').focus();return;}$('login-form').hidden=false;$('login-status').textContent=message;$('login-password').focus();}
  window.PLUPFetch=async(url,options={})=>{
    let payload;try{payload=JSON.parse(options.body||'null');}catch{}
    const form=payload?.mode==='plan'?window.PLUPPlan:payload?.mode==='forecast'?window.PLUPForecast:window.PLUPReport,revision=form?.revision();
    const saving=payload?.mode&&url.startsWith('/api/reports')&&['POST','PUT'].includes(options.method);if(saving)await window.PLUPSmart?.settle(payload.mode);
    const response=await fetch(url,{...options,headers:{...(options.headers||{}),...(['POST','PUT'].includes(options.method)?{'X-CSRF-Token':csrf}:{}),...(options.method==='PUT'&&versions.has(url.split('/').pop())?{'X-Report-Version':String(versions.get(url.split('/').pop()))}:{})}}).finally(()=>{if(saving)window.PLUPSmart?.resumeSync(payload.mode);});
    if(response.status===401)loginGate('Sesiunea a expirat. Autentifică-te din nou; valorile introduse rămân în formular.');
    if(response.ok&&payload?.mode&&revision===form?.revision()&&url.startsWith('/api/reports'))window.PLUPUI.markClean(payload.mode,payload);
    if(response.ok&&url.startsWith('/api/reports')){const result=await response.clone().json().catch(()=>null);if(result?.id&&Number.isInteger(result.version))versions.set(result.id,result.version);}
    return response;
  };
  async function checkAccess(){try{const response=await fetch('/api/session',{credentials:'same-origin'});const session=await response.json();if(!response.ok)throw Error();provider=session.provider||'password';csrf=session.csrf||'';if(session.authenticated){$('login-gate').hidden=true;if(provider==='github'&&!$('identity-logout')){const b=document.createElement('button');b.id='identity-logout';b.type='button';b.className='secondary-button';b.textContent='Deconectare';b.addEventListener('click',async()=>{if(!confirm('Te deconectezi? Salvează raportul sau ciorna înainte de a continua.'))return;b.disabled=true;try{const r=await window.PLUPFetch('/auth/logout',{method:'POST'});if(!r.ok)throw Error();for(const k of Object.keys(localStorage))if(k.startsWith('plup-'))localStorage.removeItem(k);location.replace('/');}catch{b.disabled=false;b.textContent='Reîncearcă deconectarea';}});document.querySelector('.masthead')?.append(b);}void window.PLUPSmart?.refresh();}else loginGate();}catch{$('login-loading').textContent='Serverul nu este disponibil. Reîncarcă pagina pentru a reîncerca.';}}
  $('login-form').addEventListener('submit',async e=>{
    e.preventDefault();const button=e.submitter||$('login-form').querySelector('button');if(button.disabled)return;button.disabled=true;$('login-status').textContent='Se verifică…';
    try{const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('login-password').value}),credentials:'same-origin'});const body=await response.json();if(!response.ok)throw Error(body.error||'Acces refuzat.');csrf=body.csrf;$('login-password').value='';$('login-gate').hidden=true;focusView();void window.PLUPSmart?.refresh();}catch(error){$('login-status').textContent=error.message;}finally{button.disabled=false;}
  });
  function focusView(){
    const view=$(currentView==='weekday'||currentView==='weekend'?'report-view':currentView+'-view');
    const heading=view?.querySelector('h1,h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
  }
  function show(view,{focus=true,restore=true}={}){
    scrollPositions.set(currentView,window.scrollY);
    const previous=currentView;
    const revision=++viewRevision;currentView=view;
    $('dashboard-view').hidden=view!=='dashboard';$('report-view').hidden=!['weekday','weekend'].includes(view);$('report-toolbar').hidden=!['weekday','weekend'].includes(view);$('plan-view').hidden=view!=='plan';$('forecast-view').hidden=view!=='forecast';$('history-view').hidden=view!=='history';
    if(view==='weekday'||view==='weekend'){window.PLUPReport.setMode(view);$('report-toolbar-title').textContent=names[view];}
    document.title=names[view]+' · NRG Cables · PLUP';
    document.querySelectorAll('.primary-nav [data-view]').forEach(button=>{
      const selected=button.dataset.view===view||(button.dataset.view==='weekday'&&view==='weekend');
      if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
    });
    const restoreScroll=()=>requestAnimationFrame(()=>{
      if(revision!==viewRevision)return;
      if(focus&&previous!==view)focusView();
      window.scrollTo({top:restore?(scrollPositions.get(view)||0):0,behavior:'instant'});
    });
    if(view==='history')void history().finally(restoreScroll);
    else if(view==='dashboard')Promise.resolve(window.PLUPSmart?.refresh()).finally(restoreScroll);
    else restoreScroll();
  }
  async function history(more=false){
    const revision=++historyRevision,list=$('history-list');if(!more){historyOffset=0;list.textContent='Se încarcă istoricul…';}$('history-status').textContent='';
    try{
      const response=await window.PLUPFetch(`/api/reports?limit=100&offset=${historyOffset}`,{credentials:'same-origin'});if(!response.ok)throw Error('Istoricul nu este disponibil.');const records=await response.json();if(revision!==historyRevision)return;
      const html=records.map(r=>`<div class="history-item"><div><b>${esc(names[r.mode])}</b><span>${esc(r.date)} · ${esc(new Date(r.updated_at||r.created_at).toLocaleString('ro-RO'))}</span></div><button type="button" data-load="${esc(r.id)}">Editează →</button><button type="button" data-versions="${esc(r.id)}" class="secondary-button">Versiuni</button></div>`).join('');
      if(more)list.insertAdjacentHTML('beforeend',html);else list.innerHTML=html||'Nu există rapoarte salvate încă.';historyOffset+=records.length;$('more-history').hidden=records.length<100;
    }catch(e){if(revision===historyRevision)$('history-status').textContent=e.message;}
  }
  async function startNew(mode,button){
    if(opening||!window.PLUPUI.confirmReplace(mode)||!window.PLUPSmart?.confirmNew(mode))return;opening=true;button.disabled=true;$('dashboard-status').textContent='Se încarcă ultimele valori…';const revision=viewRevision;
    try{
      const response=await window.PLUPFetch('/api/reports/latest?mode='+encodeURIComponent(mode),{credentials:'same-origin'});if(!response.ok)throw Error('Nu am putut încărca ultimele valori. Reîncearcă.');const {payload}=await response.json();if(revision!==viewRevision)return;
      const today=new Date().toLocaleDateString('sv-SE');
      if(mode==='plan')window.PLUPPlan.load(payload?{...payload,date:today}:{mode,date:today,week:'',incoming:'',rows:[{material:'AL'},{material:'CU'}]},null);
      else if(mode==='forecast')window.PLUPForecast.load(payload?{...payload,date:today}:{mode,date:today,rows:[{material:'AL'}]},null);
      else window.PLUPReport.newFrom(payload,mode,today);
      window.PLUPUI.markClean(mode);window.PLUPSmart?.clearImport(mode);show(mode,{restore:false});
      $(mode==='plan'?'plan-status':mode==='forecast'?'forecast-status':'api-status').textContent=payload?'Raport nou, precompletat cu ultimele valori. Verifică data și actualizează cantitățile.':'Raport nou. Completează valorile.';
      $('dashboard-status').textContent='';
    }catch(error){$('dashboard-status').textContent=error.message;}finally{opening=false;button.disabled=false;}
  }
  document.addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;if(b.classList.contains('dashboard-card'))void startNew(b.dataset.view,b);else show(b.dataset.view);});
  $('refresh-history').addEventListener('click',()=>history());$('more-history').addEventListener('click',()=>history(true));
  $('history-list').addEventListener('click',async e=>{
    const b=e.target.closest('[data-load]');if(!b||opening)return;opening=true;b.disabled=true;$('history-status').textContent='Se deschide raportul…';const revision=viewRevision;
    try{const response=await window.PLUPFetch('/api/reports/'+encodeURIComponent(b.dataset.load),{credentials:'same-origin'});if(!response.ok)throw Error('Raportul nu a putut fi deschis.');const record=await response.json();if(revision!==viewRevision||!window.PLUPUI.confirmReplace(record.mode))return;
      if(record.mode==='plan'){window.PLUPPlan.load(record.payload,record.id);show('plan');}else if(record.mode==='forecast'){window.PLUPForecast.load(record.payload,record.id);show('forecast');}else{show(record.mode);window.PLUPReport.load(record.payload,record.id);}
      window.PLUPUI.markClean(record.mode);$('history-status').textContent='';
    }catch(err){$('history-status').textContent=err.message;}finally{opening=false;b.disabled=false;}
  });
  window.PLUPDashboard={show,current:()=>currentView,refreshHistory:()=>history(),setVersion:(id,version)=>versions.set(id,version),getVersion:id=>versions.get(id)??0};
  show('dashboard',{focus:false});checkAccess();
})();
