(() => {
  const $=id=>document.getElementById(id);
  let csrf='';
  window.PLUPFetch=(url,options={})=>fetch(url,{...options,headers:{...(options.headers||{}),...(options.method==='POST'?{'X-CSRF-Token':csrf}:{})}});
  async function checkAccess(){try{const response=await fetch('/api/session',{credentials:'same-origin'});const session=await response.json();if(!response.ok)throw Error();csrf=session.csrf||'';if(session.authenticated){$('login-gate').hidden=true;}else{$('login-loading').hidden=true;$('login-form').hidden=false;}}catch{$('login-loading').textContent='Serverul nu este disponibil. Reîncearcă după ce revine conexiunea.';}}
  $('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-status').textContent='Se verifică…';try{const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('login-password').value}),credentials:'same-origin'});const body=await response.json();if(!response.ok)throw Error(body.error||'Acces refuzat.');csrf=body.csrf;$('login-password').value='';$('login-gate').hidden=true;}catch(error){$('login-status').textContent=error.message;}});
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names={plan:'Plan de producție',weekday:'Raport zilnic',weekend:'Raport weekend'};
  function show(view){
    $('dashboard-view').hidden=view!=='dashboard';$('report-view').hidden=!['weekday','weekend'].includes(view);$('report-toolbar').hidden=!['weekday','weekend'].includes(view);$('plan-view').hidden=view!=='plan';$('history-view').hidden=view!=='history';
    if(view==='weekday'||view==='weekend'){window.PLUPReport.setMode(view);$('report-toolbar-title').textContent=names[view];}
    if(view==='history')history();window.scrollTo({top:0,behavior:'instant'});
  }
  let historyOffset=0;
  async function history(more=false){
    const list=$('history-list');if(!more){historyOffset=0;list.textContent='Se încarcă istoricul…';}$('history-status').textContent='';
    try{
      const response=await window.PLUPFetch(`/api/reports?limit=100&offset=${historyOffset}`,{credentials:'same-origin'});
      if(!response.ok)throw Error('Istoricul nu este disponibil.');
      const records=await response.json();
      const html=records.map(r=>`<div class="history-item"><div><b>${esc(names[r.mode])}</b><span>${esc(r.date)} · ${esc(new Date(r.created_at).toLocaleString('ro-RO'))}</span></div><button type="button" data-load="${esc(r.id)}">Deschide →</button></div>`).join('');
      if(more)list.insertAdjacentHTML('beforeend',html);else list.innerHTML=html||'Nu există rapoarte salvate încă.';
      historyOffset+=records.length;$('more-history').hidden=records.length<100;
    }catch(e){$('history-status').textContent=e.message;}
  }
  document.addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b)show(b.dataset.view);});
  $('refresh-history').addEventListener('click',()=>history());
  $('more-history').addEventListener('click',()=>history(true));
  $('history-list').addEventListener('click',async e=>{const b=e.target.closest('[data-load]');if(!b)return;$('history-status').textContent='Se deschide raportul…';try{const response=await window.PLUPFetch('/api/reports/'+encodeURIComponent(b.dataset.load),{credentials:'same-origin'});if(!response.ok)throw Error('Raportul nu a putut fi deschis.');const record=await response.json();if(record.mode==='plan'){window.PLUPPlan.load(record.payload);show('plan');}else{window.PLUPReport.load(record.payload);show(record.mode);}$('history-status').textContent='';}catch(err){$('history-status').textContent=err.message;}});
  show('dashboard');
  checkAccess();
})();
