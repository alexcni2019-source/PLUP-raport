(() => {
  'use strict';
  const keys = ['al','cu','backlogAl','backlogCu','wasteAl','wasteCu'];
  const extraFields = [['op_asumreal','Asumat / realizat (t + %)'],['op_status','Realizat vs. status'],['op_plan','Realizat vs. plan'],['op_previz','Previzionat schimbul 1'],['op_backal','Backlog aluminiu operațional'],['op_backcu','Backlog cupru operațional'],['op_rigid1','SF așteptare · Rigid 1 (km)'],['op_rigid2','SF așteptare · Rigid 2 (km)'],['op_rigid3','SF așteptare · Rigid 3 (km)'],['op_multi1','SF așteptare · Multifir 8 căi 1 (t)'],['op_multi2','SF așteptare · Multifir 8 căi 2 (t)'],['op_niehoff','SF așteptare · 16 căi Niehoff (t)'],['op_beta3','SF așteptare · 16 căi Beta 3 (t)'],['op_stocal','Stoc aluminiu'],['op_stoccu','Stoc cupru'],['obs','Observații']];
  const groups = [
    ['PRODUCȚIE PREDATĂ', [['al','Aluminiu predat'],['cu','Cupru predat']]],
    ['BACKLOG PREDAT', [['backlogAl','Aluminiu backlog'],['backlogCu','Cupru backlog']]],
    ['DEȘEU', [['wasteAl','Deșeu aluminiu'],['wasteCu','Deșeu cupru']]]
  ];
  const $ = id => document.getElementById(id);
  const number = x => { const n = Number(String(x ?? '').replace(',','.')); return Number.isFinite(n) && n >= 0 ? n : 0; };
  const fmt = (n, digits=2) => n.toLocaleString('ro-RO',{minimumFractionDigits:digits,maximumFractionDigits:digits});
  const esc = x => String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dateKey = date => [date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');
  const parseDate = key => { const [y,m,d]=key.split('-').map(Number); return new Date(y,m-1,d,12); };
  const shiftDate = (key,days) => { const date=parseDate(key); date.setDate(date.getDate()+days); return dateKey(date); };
  const labelDate = key => new Intl.DateTimeFormat('ro-RO',{day:'2-digit',month:'long',year:'numeric'}).format(parseDate(key));
  const dayName = key => new Intl.DateTimeFormat('ro-RO',{weekday:'long'}).format(parseDate(key));
  const today=dateKey(new Date());
  let state={mode:'weekday',date:today,selectedDate:today,values:{}};
  let loadedId=null;
  const startFriday = key => shiftDate(key,(5-parseDate(key).getDay()+7)%7 === 0 ? 0 : (5-parseDate(key).getDay()+7)%7-7);
  function save(){}
  function dates(){return state.mode==='weekend'?[state.date,shiftDate(state.date,1),shiftDate(state.date,2)]:[state.date];}
  function valuesFor(date){return state.values[date]||{};}
  function calculate(date){const v=valuesFor(date);const handed=number(v.al)+number(v.cu),backlog=number(v.backlogAl)+number(v.backlogCu),waste=number(v.wasteAl)+number(v.wasteCu),processed=handed+waste;return {handed,backlog,waste,processed,percent:processed?100*waste/processed:0};}
  function setupInputs(){
    $('entry-list').innerHTML=dates().map((date,i)=>`<article class="day-entry"><div class="day-title"><strong>${state.mode==='weekend'?['Vineri','Sâmbătă','Duminică'][i]:'Zi selectată'}</strong><span>${labelDate(date)}</span></div>${groups.map(([title,fields])=>`<div class="field-group"><div class="group-label">${title}</div><div class="input-grid">${fields.map(([key,label])=>`<label class="value-field"><span>${label}</span><div class="input-wrap"><input type="text" inputmode="decimal" autocomplete="off" data-date="${date}" data-key="${key}" aria-label="${label}, ${dayName(date)} ${labelDate(date)}" placeholder="0,00" value="${esc(valuesFor(date)[key])}"><em>t</em></div></label>`).join('')}</div></div>`).join('')}<details class="extras"><summary>Indicatori operaționali <span>opțional</span></summary><div class="extra-grid">${extraFields.map(([key,label])=>`<label class="value-field"><span>${label}</span><input type="text" maxlength="120" autocomplete="off" data-date="${date}" data-key="${key}" value="${esc(valuesFor(date)[key])}" placeholder="—"></label>`).join('')}</div></details></article>`).join('');
  }
  function renderReport(){
    const ds=dates();const weekend=state.mode==='weekend';
    $('paper-heading').textContent=weekend?'Raport weekend':'Raport zilnic';
    $('paper-period').textContent=weekend?`${labelDate(ds[0])} – ${labelDate(ds[2])}`:labelDate(ds[0]);
    $('total-period').textContent=weekend?'· VINERI – DUMINICĂ':'';
    $('paper-days').innerHTML=ds.map((date,i)=>{const v=valuesFor(date),c=calculate(date);const extras=extraFields.filter(([key])=>String(v[key]??'').trim());return `<div class="paper-day"><div class="paper-day-title"><strong>${weekend?['Vineri','Sâmbătă','Duminică'][i]:'Producție zilnică'}</strong><span>${labelDate(date)}</span></div><div class="paper-data"><div class="paper-row"><span>Aluminiu predat</span><strong>${fmt(number(v.al))} t</strong></div><div class="paper-row"><span>Cupru predat</span><strong>${fmt(number(v.cu))} t</strong></div><div class="paper-row"><span>Backlog aluminiu</span><strong>${fmt(number(v.backlogAl))} t</strong></div><div class="paper-row"><span>Backlog cupru</span><strong>${fmt(number(v.backlogCu))} t</strong></div><div class="paper-row"><span>Deșeu aluminiu</span><strong>${fmt(number(v.wasteAl))} t</strong></div><div class="paper-row"><span>Deșeu cupru</span><strong>${fmt(number(v.wasteCu))} t</strong></div></div><div class="paper-day-summary"><span>Predat: ${fmt(c.handed)} t</span><span>Procesat: ${fmt(c.processed)} t</span><strong>Deșeu: ${fmt(c.percent,1)}%</strong></div>${extras.length?`<div class="paper-extras"><b>INDICATORI OPERAȚIONALI</b>${extras.map(([key,label])=>`<div><span>${esc(label)}</span><strong>${esc(v[key])}</strong></div>`).join('')}</div>`:''}</div>`}).join('');
    const total=ds.reduce((sum,date)=>{const c=calculate(date);for(const k of ['handed','backlog','waste','processed'])sum[k]+=c[k];return sum},{handed:0,backlog:0,waste:0,processed:0});
    $('total-handed').innerHTML=`${fmt(total.handed)} <small>t</small>`;
    $('total-backlog').innerHTML=`${fmt(total.backlog)} <small>t</small>`;
    $('total-waste').innerHTML=`${fmt(total.waste)} <small>t</small>`;
    $('total-processed').innerHTML=`${fmt(total.processed)} <small>t</small>`;
    $('total-percent').textContent=fmt(total.processed?total.waste/total.processed*100:0,1)+'%';
    document.title=`Raport PLUP · ${weekend?'Weekend ':' '}${labelDate(ds[0])} · NRG Cables`;
  }
  function payload(){const current={};for(const date of dates()){const raw=valuesFor(date);current[date]=Object.fromEntries([...keys,...extraFields.map(x=>x[0])].map(key=>[key,raw[key]??'']));}return {mode:state.mode,date:state.date,values:current};}
  function render(){document.querySelector(`input[name=mode][value=${state.mode}]`).checked=true;$('report-date').value=state.selectedDate||state.date;$('date-label').textContent='Data aleasă';$('date-hint').textContent=state.mode==='weekend'?`Raportul include vineri–duminică (${dates().map(labelDate).join(' · ')}). Ziua aleasă rămâne ${labelDate(state.selectedDate||state.date)}.`:'Raport pentru o singură zi, inclusiv sâmbătă sau duminică.';setupInputs();renderReport();save();}
  document.querySelectorAll('input[name=mode]').forEach(input=>input.addEventListener('change',()=>{const selected=state.selectedDate||state.date;state.mode=input.value;state.date=state.mode==='weekend'?startFriday(selected):selected;state.selectedDate=selected;render();}));
  $('report-date').addEventListener('change',e=>{if(!e.target.value)return;const previous=state.date;const chosen=e.target.value;state.selectedDate=chosen;state.date=state.mode==='weekend'?startFriday(chosen):chosen;if(state.mode==='weekday'&&previous!==chosen&&state.values[previous]){state.values[chosen]=state.values[previous];delete state.values[previous];}render();});
  $('entry-list').addEventListener('input',e=>{const input=e.target;if(!input.matches('[data-key]'))return;const raw=input.value.trim();if(keys.includes(input.dataset.key)&&raw&&!/^\d{0,7}(?:[.,]\d{0,4})?$/.test(raw)){input.value=state.values[input.dataset.date]?.[input.dataset.key]??'';return;}const date=input.dataset.date;state.values[date]??={};state.values[date][input.dataset.key]=raw;save();renderReport();});
  $('reset-button').addEventListener('click',()=>{for(const date of dates())delete state.values[date];render();});
  $('save-report-button').addEventListener('click',async()=>{const button=$('save-report-button');button.disabled=true;$('api-status').textContent='Se salvează…';try{const response=await window.PLUPFetch(loadedId?'/api/reports/'+encodeURIComponent(loadedId):'/api/reports',{method:loadedId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload()),credentials:'same-origin'});const body=await response.json();if(!response.ok)throw new Error(body.error||'Salvarea a eșuat.');loadedId=body.id;$('api-status').textContent='Raportul din istoric a fost actualizat. Poți genera PNG-ul acum.';}catch(e){$('api-status').textContent=e.message;}finally{button.disabled=false;}});
  $('generate-report-image').addEventListener('click',async()=>{
    const button=$('generate-report-image'),gallery=$('report-images');button.disabled=true;gallery.replaceChildren();$('api-status').textContent='Se generează imaginile…';
    try {
      const labels=state.mode==='weekend'?['Vineri','Sâmbătă','Duminică','Total weekend']:['Raport zilnic'];
      const order=state.mode==='weekend'?[...Array(labels.length).keys()].sort((a,b)=>a===dates().indexOf(state.selectedDate)?-1:b===dates().indexOf(state.selectedDate)?1:a-b):[0];
      for(const i of order){
        const response=await window.PLUPFetch(`/api/render?page=${i}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload()),credentials:'same-origin'});
        if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'Generarea nu este disponibilă.');}
        const blob=await response.blob();if(blob.type!=='image/png')throw Error('Răspuns imagine invalid.');
        const url=URL.createObjectURL(blob),item=document.createElement('div'),title=document.createElement('strong'),img=document.createElement('img'),link=document.createElement('a');
        item.className='image-result';title.textContent=`${labels[i]} · ${i<dates().length?labelDate(dates()[i]):'total'}`;img.src=url;img.alt=`Previzualizare ${labels[i]} PLUP`;link.href=url;link.download=`NRG_PLUP_${i<dates().length?dates()[i]:state.date+'_total'}.png`;link.textContent='Descarcă PNG ↓';item.append(title,img,link);gallery.append(item);
      }
      $('api-status').textContent='Imaginile sunt gata. Pe iPhone, poți și apăsa lung pe imagine pentru a o salva.';
    }catch(e){$('api-status').textContent=e.message;}finally{button.disabled=false;}
  });
  if(matchMedia('(hover:hover) and (pointer:fine)').matches){document.querySelectorAll('.panel').forEach(panel=>panel.addEventListener('pointermove',e=>{const r=panel.getBoundingClientRect();panel.style.setProperty('--cursor-x',`${e.clientX-r.left}px`);panel.style.setProperty('--cursor-y',`${e.clientY-r.top}px`);}));}
  window.PLUPReport={setMode(mode){if(mode!==state.mode)loadedId=null;state.mode=mode;const selected=state.selectedDate||state.date;state.date=mode==='weekend'?startFriday(selected):selected;state.selectedDate=selected;render();},load(data,id){loadedId=id||null;state={mode:data.mode,date:data.date,selectedDate:data.date,values:data.values};render();},payload};
  render();
})();
