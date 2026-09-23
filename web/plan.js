(() => {
  'use strict';
  const fields=[['client','Client','text'],['product','Produs','text'],['planned','Metal planificat (t)','decimal'],['handed','Metal predat (t)','decimal'],['wire','Sârmă (t)','decimal'],['spool','Stoc lită (t)','decimal'],['bar','Stoc fune / bară (km)','decimal'],['vane','Stoc vane (km)','decimal'],['cable','Stoc cablat (km)','decimal'],['mi','Stoc M.I. (km)','decimal'],['armored','Stoc armat (km)','decimal'],['mf','Stoc M.F. (km)','decimal'],['goods','Marfă predată (km)','decimal'],['notes','Observații','text']];
  const number=x=>Number(String(x||'0').replace(',','.'))||0;
  const fmt=x=>x.toLocaleString('ro-RO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const $=id=>document.getElementById(id);
  let rows=[{material:'AL',client:'',product:''},{material:'CU',client:'',product:''}];
  let reviewFields=new Set(),importNeedsReview=false;
  $('plan-date').value=new Date().toLocaleDateString('sv-SE');
  function render(){
    $('plan-rows').innerHTML=['AL','CU'].map(material=>`<div class="plan-group"><h3>${material==='AL'?'Aluminiu':'Cupru'} <small>${rows.filter(r=>r.material===material).length} rânduri</small></h3>${rows.map((r,i)=>r.material!==material?'':`<article class="plan-row"><div class="plan-row-head"><strong>${material} · poziția ${rows.slice(0,i+1).filter(x=>x.material===material).length}</strong><button type="button" data-remove="${i}" aria-label="Șterge rândul ${i+1}">Șterge</button></div><div class="plan-field-grid">${fields.map(([key,label,type])=>`<label class="plan-field ${reviewFields.has(i+':'+key)?'needs-review':''}"><span>${label}${reviewFields.has(i+':'+key)?' · verifică':''}</span><input data-index="${i}" data-key="${key}" type="text" ${type==='decimal'?'inputmode="decimal"':'autocomplete="off"'} maxlength="120" value="${esc(r[key])}" placeholder="${type==='decimal'?'0,00':'—'}"></label>`).join('')}</div></article>`).join('')}</div>`).join('');
    totals();
  }
  function totals(){const sum=material=>rows.filter(r=>r.material===material).reduce((a,r)=>{for(const k of ['planned','handed','wire'])a[k]+=number(r[k]);return a},{planned:0,handed:0,wire:0});const al=sum('AL'),cu=sum('CU');$('plan-totals').innerHTML=`<div><span>Total AL planificat / predat</span><strong>${fmt(al.planned)} / ${fmt(al.handed)} t</strong></div><div><span>Total CU planificat / predat</span><strong>${fmt(cu.planned)} / ${fmt(cu.handed)} t</strong></div><div><span>Total general planificat / predat</span><strong>${fmt(al.planned+cu.planned)} / ${fmt(al.handed+cu.handed)} t</strong></div>`;}
  $('plan-rows').addEventListener('input',e=>{const input=e.target;if(!input.matches('[data-key]'))return;const key=input.dataset.key;const raw=input.value.trim();if(fields.find(f=>f[0]===key)?.[2]==='decimal'&&raw&&!/^\d{0,7}(?:[.,]\d{0,4})?$/.test(raw)){input.value=rows[+input.dataset.index][key]??'';return;}rows[+input.dataset.index][key]=raw;reviewFields.delete(input.dataset.index+':'+key);input.closest('.plan-field').classList.remove('needs-review');totals();});
  $('plan-rows').addEventListener('click',e=>{const b=e.target.closest('[data-remove]');if(!b)return;rows.splice(+b.dataset.remove,1);render();});
  for(const [id,material] of [['add-al','AL'],['add-cu','CU']])$(id).addEventListener('click',()=>{rows.push({material});render();document.querySelector(`[data-index="${rows.length-1}"][data-key="client"]`)?.focus();});
  function payload(){return {mode:'plan',date:$('plan-date').value,week:$('plan-week').value.trim(),incoming:$('plan-incoming').value.trim(),rows:rows.map(r=>Object.fromEntries([['material',r.material],...fields.map(([key])=>[key,r[key]??''])]))};}
  async function post(path){const response=await window.PLUPFetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload()),credentials:'same-origin'});if(!response.ok){const e=await response.json().catch(()=>({}));throw Error(e.error||'Operația nu a reușit.');}return response;}
  $('save-plan').addEventListener('click',async()=>{if(importNeedsReview&&!$('plan-confirm').checked){$('plan-status').textContent='Verifică valorile și bifează confirmarea înainte de salvare.';$('plan-review').scrollIntoView({behavior:'smooth',block:'center'});return;}const b=$('save-plan');b.disabled=true;$('plan-status').textContent='Se salvează…';try{await post('/api/reports');$('plan-status').textContent='Planul a fost salvat în istoric.';}catch(e){$('plan-status').textContent=e.message;}finally{b.disabled=false;}});
  $('image-plan').addEventListener('click',async()=>{const b=$('image-plan');b.disabled=true;$('plan-status').textContent='Se generează imaginea…';try{const response=await post('/api/render'),blob=await response.blob();if(blob.type!=='image/png')throw Error('Răspuns imagine invalid.');const url=URL.createObjectURL(blob),wrap=document.createElement('div'),img=document.createElement('img'),link=document.createElement('a');wrap.className='image-result';img.src=url;img.alt='Previzualizare plan PLUP';link.href=url;link.download=`NRG_PLUP_plan_${$('plan-date').value}.png`;link.textContent='Descarcă PNG ↓';wrap.append(img,link);$('plan-images').replaceChildren(wrap);$('plan-status').textContent='Imaginea este gata. Pe iPhone, poți apăsa lung pe ea pentru a o salva.';}catch(e){$('plan-status').textContent=e.message;}finally{b.disabled=false;}});
  async function imagePayload(file){
    if(file.size>20_000_000)throw Error('Imaginea este prea mare. Folosește o captură sub 20 MB.');
    const url=URL.createObjectURL(file),photo=new Image();
    try{
      photo.src=url;
      await photo.decode();
      if(photo.naturalWidth*photo.naturalHeight>30_000_000)throw Error('Imaginea are rezoluție prea mare.');
      const scale=Math.min(1,3000/photo.naturalWidth,3000/photo.naturalHeight);
      const canvas=document.createElement('canvas');
      canvas.width=Math.round(photo.naturalWidth*scale);canvas.height=Math.round(photo.naturalHeight*scale);
      canvas.getContext('2d').drawImage(photo,0,0,canvas.width,canvas.height);
      const jpeg=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.9));
      if(!jpeg||jpeg.size>6_000_000)throw Error('Imaginea este prea mare după pregătire. Încearcă o captură mai mică.');
      return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Nu am putut citi imaginea.'));reader.readAsDataURL(jpeg);});
    }catch(error){if(error.name==='EncodingError')throw Error('Formatul imaginii nu poate fi citit. Încearcă JPG sau PNG.');throw error;}
    finally{URL.revokeObjectURL(url);}
  }
  let importBusy=false;
  const pasteHint='Pe iPhone, dacă butonul nu poate citi clipboardul, ține apăsat aici și alege „Lipește”. Pe PC poți apăsa Ctrl+V sau ⌘V.';
  async function importImage(file){
    if(importBusy)return;
    if((importNeedsReview||rows.some(r=>fields.some(([key])=>String(r[key]??'').trim())))&&!window.confirm('Importul va înlocui rândurile din formular. Continui?'))return;
    importBusy=true;$('plan-file').disabled=true;$('plan-paste').disabled=true;$('plan-paste-zone').setAttribute('aria-busy','true');
    $('plan-status').textContent='Citesc tabelul din imagine… Poate dura câteva zeci de secunde.';
    try{
      const image=await imagePayload(file);
      const response=await window.PLUPFetch('/api/plan/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image}),credentials:'same-origin'});
      const draft=await response.json();if(!response.ok)throw Error(draft.error||'Nu am putut citi tabelul.');
      rows=draft.rows;reviewFields=new Set(draft.review.map(item=>item.row+':'+item.field));
      if(draft.date)$('plan-date').value=draft.date;
      if(draft.week)$('plan-week').value=draft.week;
      if(draft.incoming)$('plan-incoming').value=draft.incoming;
      importNeedsReview=true;$('plan-confirm').checked=false;$('plan-review').hidden=false;
      $('plan-review-message').textContent=`Am extras ${rows.length} rânduri. ${reviewFields.size} câmpuri sunt marcate pentru verificare. Compară toate valorile cu fotografia înainte să salvezi.`;
      render();$('plan-status').textContent='Datele au fost adăugate în formular. Imaginea nu este stocată.';
      $('plan-review').scrollIntoView({behavior:'smooth',block:'start'});
    }catch(error){$('plan-status').textContent=error.message;}
    finally{importBusy=false;$('plan-file').disabled=false;$('plan-paste').disabled=false;$('plan-paste-zone').removeAttribute('aria-busy');}
  }
  $('plan-file').addEventListener('change',async e=>{
    const file=e.target.files?.[0];if(!file)return;
    try{await importImage(file);}finally{e.target.value='';}
  });
  $('plan-paste').addEventListener('click',async()=>{
    if(importBusy)return;
    if(!navigator.clipboard?.read){$('plan-status').textContent='Browserul nu permite citirea directă. Ține apăsat în caseta de lipire și alege „Lipește”.';$('plan-paste-zone').focus();return;}
    try{
      // The read call happens directly in the click gesture, as required on iOS.
      const items=await navigator.clipboard.read();
      for(const item of items){
        const kind=item.types.find(type=>type.startsWith('image/'));
        if(kind){await importImage(await item.getType(kind));return;}
      }
      $('plan-status').textContent='Clipboardul nu conține o imagine. Copiază fotografia, apoi încearcă din nou.';
    }catch(error){
      $('plan-status').textContent='Accesul la clipboard nu a fost permis. Ține apăsat în caseta de lipire și alege „Lipește”.';
      $('plan-paste-zone').focus();
    }
  });
  document.addEventListener('paste',event=>{
    if($('plan-view').hidden)return;
    if(importBusy){if(event.target===$('plan-paste-zone'))event.preventDefault();return;}
    const file=Array.from(event.clipboardData?.items||[]).find(item=>item.type.startsWith('image/'))?.getAsFile();
    if(!file){
      if(event.target===$('plan-paste-zone')){event.preventDefault();$('plan-status').textContent='Clipboardul nu conține o imagine. Copiază fotografia și încearcă din nou.';}
      return;
    }
    event.preventDefault();
    void importImage(file);
  });
  $('plan-paste-zone').addEventListener('beforeinput',event=>{if(event.inputType!=='insertFromPaste')event.preventDefault();});
  $('plan-paste-zone').addEventListener('blur',()=>{$('plan-paste-zone').textContent=pasteHint;});
  window.PLUPPlan={load(data){$('plan-date').value=data.date;$('plan-week').value=data.week;$('plan-incoming').value=data.incoming||'';rows=data.rows;reviewFields.clear();importNeedsReview=false;$('plan-review').hidden=true;render();},payload};
  render();
})();
