(() => {
 'use strict';
 const tables=new Map(),pages=new Map(),$=id=>document.getElementById(id);
 const clone=x=>JSON.parse(JSON.stringify(x));
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const suffix=mode=>['weekday','weekend'].includes(mode)?'report':mode;
 const controller=mode=>mode==='plan'?window.PLUPPlan:mode==='forecast'?window.PLUPForecast:window.PLUPReport;
 const fields={plan:['material','client','product','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','notes'],forecast:['material','product','km','tons','client','measure','status','notes','order','priority','drumLength'],report:['al','cu','backlogAl','backlogCu','wasteAl','wasteCu','op_asumreal','op_status','op_plan','op_previz','op_backal','op_backcu','op_rigid1','op_rigid2','op_rigid3','op_multi1','op_multi2','op_niehoff','op_beta3','op_stocal','op_stoccu','obs']};
 const numeric=new Set(['drumLength','km','tons','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','al','cu','backlogAl','backlogCu','wasteAl','wasteCu']);
 const convert=(v,k)=>{let s=String(v??'').trim();if(s==='—'||s==='-')return '';if(k==='drumLength')s=s.replace(/\s*m$/i,'');if(numeric.has(k))s=s.replace(/\s/g,'').replace(/(?:tone|tona|km|t)$/i,'');return s;};
 const kmColumns=t=>{
  const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const locate=names=>{const matches=t.rows[t.header].map((v,i)=>names.includes(norm(v))?i:-1).filter(i=>i>=0);return matches.length===1?matches[0]:null};
  return [locate(['km porniti','km pornit','kilometri porniti']),locate(['km predati','km predat','kilometri predati'])];
 };
 const near=(row,pair)=>{
  if(pair.some(i=>i===null))return false;
  const parse=v=>{const s=String(v??'').toLowerCase().replace(/\s/g,'').replace(/km$/,'');return /^\d+(?:[.,]\d+)?$/.test(s)?s.replace(',','.'):null};
  const a=parse(row[pair[0]]),b=parse(row[pair[1]]);if(a===null||b===null)return false;const parts=[a.split('.'),b.split('.')],precision=Math.max(1,...parts.map(p=>(p[1]||'').length)),scaled=parts.map(p=>BigInt(p[0]+(p[1]||'').padEnd(precision,'0'))),diff=scaled[0]-scaled[1];return scaled[0]>0n&&(diff<0n?-diff:diff)<=2n*10n**BigInt(precision-1);
 };
 function colorKm(mode){
  const t=tables.get(mode),panel=$('source-editor-'+suffix(mode));if(!t||!panel||mode!=='plan')return;const pair=kmColumns(t);
  panel.querySelectorAll('textarea[data-source-row]').forEach(n=>{const ri=Number(n.dataset.sourceRow),ci=Number(n.dataset.sourceCol),row=t.rows[ri],total=/^(total|intr[aă]ri)/i.test(row.slice(0,3).join(' ').trim());const green=ri>t.header&&!total&&pair.includes(ci)&&near(row,pair);n.closest('td').classList.toggle('km-complete',green);if(green)n.title='Diferență de cel mult 0,2 km între porniți și predați';else n.removeAttribute('title');});
 }
 const day=(stamp,n)=>{const d=new Date(stamp+'T12:00:00');d.setDate(d.getDate()+n);return d.toLocaleDateString('sv-SE');};
 function weekFor(table,fallback=''){
  const weeks=new Set();for(const row of table.rows.slice(0,table.header))for(const cell of row)for(const match of String(cell).matchAll(/(?:^|[^\w])(?:wk|w|s[aă]pt[aă]m[aâ]na)\s*[-.:]?\s*(\d{1,2})(?!\d)/gi))weeks.add(Number(match[1]));
  if(weeks.size>1||[...weeks].some(w=>w<1||w>53))throw Error('Săptămâna din titlul tabelului este ambiguă sau invalidă.');
  return weeks.size?'W'+[...weeks][0]:fallback;
 }
 function attach(base){
  const source=tables.get(base.mode);if(!source)return base;
  const table=clone(source),cols=table.columns,type=suffix(base.mode);
  if(base.mode==='plan')base.week=weekFor(table,base.week);
  if(type==='report'){
   base.values={};
   for(const rec of table.records){const row=table.rows[rec.row],stamp=day(base.date,rec.day);base.values[stamp]=Object.fromEntries(fields.report.map(k=>[k,Number.isInteger(cols[k])?convert(row[cols[k]],k):'']));
    if(Number.isInteger(cols.date)&&base.date!==table.date){const previous=row[cols.date]||'';row[cols.date]=/^\d{1,2}[./]/.test(previous)?stamp.split('-').reverse().join(previous.includes('/')?'/':'.'):stamp;}
   }
  }else{
   let group='AL';const materials=new Map();for(let ri=table.header+1;ri<table.rows.length;ri++){const token=String(table.rows[ri][Number.isInteger(cols.material)?cols.material:0]||'').trim().toUpperCase().replace(':','');if(['CU','CUPRU','COPPER'].includes(token))group='CU';if(['AL','ALUMINIU','ALUMINIUM'].includes(token))group='AL';materials.set(ri,group);}
   base.rows=table.records.filter(rec=>table.rows[rec.row].some(v=>String(v).trim())).map(rec=>{
    const row=table.rows[rec.row];const mapped=Object.fromEntries(fields[type].filter(k=>k!=='material').map(k=>[k,Number.isInteger(cols[k])?convert(row[cols[k]],k):'']));
    const material=Number.isInteger(cols.material)?String(row[cols.material]||'').trim().toUpperCase().replace(':',''):'';
    return {material:['CU','CUPRU','COPPER'].includes(material)?'CU':['AL','ALUMINIU','ALUMINIUM'].includes(material)?'AL':materials.get(rec.row)||rec.material,...mapped};
   });
  }
  if(base.date!==table.date){
   const old=table.date.split('-'),next=base.date.split('-');
   for(let ri=0;ri<table.header;ri++)table.rows[ri]=table.rows[ri].map(v=>v.replaceAll(old.join('-'),next.join('-')).replaceAll([...old].reverse().join('.'),[...next].reverse().join('.')).replaceAll([...old].reverse().join('/'),[...next].reverse().join('/')));
  }
  table.date=base.date;return {...base,sourceTable:table};
 }
 function visibility(mode,active){
  const type=suffix(mode),root=$(type==='report'?'report-view':type+'-view');if(!root)return;
  const selectors=type==='report'?'#entry-list,#print-report':`#${type}-rows,#${type}-totals,#${type==='plan'?'add-al':'forecast-add-al'},#${type==='plan'?'add-cu':'forecast-add-cu'}`;
  root.querySelectorAll(selectors).forEach(el=>el.classList.toggle('source-hidden',active));
 }
 function render(mode){
  const type=suffix(mode),root=$(type==='report'?'report-view':type+'-view');if(!root)return;
  let panel=$('source-editor-'+type);const current=controller(mode)?.payload();if(current?.mode===mode&&current.sourceTable)tables.set(mode,current.sourceTable);const table=tables.get(mode);visibility(mode,!!table);
  if(!panel){panel=document.createElement('section');panel.id='source-editor-'+type;panel.className='source-editor';const anchor=root.querySelector(type==='report'?'.date-hint':'.plan-controls');anchor.after(panel);}
  panel.hidden=!table;if(!table)return;
  const cols=Math.max(...table.rows.map(r=>r.length)),page=Math.min(pages.get(mode)||0,Math.floor((table.rows.length-1)/25));pages.set(mode,page);const start=page*25,headers=table.rows[table.header];
  panel.innerHTML=`<div class="smart-heading"><h3>Tabelul tău · toate coloanele</h3><span>${table.rows.length} rânduri · ${cols} coloane</span></div><p class="smart-note">Antetele, ordinea, celulele goale și totalurile din Excel se păstrează în PNG și în istoric. Poți edita valorile aici. Totalurile scrise în tabel nu se recalculează automat; verifică-le după editare.</p><div class="smart-scroll source-grid"><table><tbody>${table.rows.slice(start,start+25).map((row,offset)=>{const ri=start+offset;return `<tr class="${ri===table.header?'source-header':''}"><th scope="row">${ri+1}</th>${Array.from({length:cols},(_,ci)=>ri===table.header?`<th scope="col">${esc(row[ci]||'')}</th>`:`<td><textarea rows="1" wrap="off" maxlength="1000" ${table.columns.date===ci&&table.records.some(r=>r.row===ri)?'readonly':''} data-source-mode="${mode}" data-source-row="${ri}" data-source-col="${ci}" aria-label="Rând ${ri+1}, ${esc(headers[ci]||'coloana '+(ci+1))}">${esc(row[ci]||'')}</textarea></td>`).join('')}</tr>`;}).join('')}</tbody></table></div><div class="source-toolbar"><span>Rânduri ${start+1}–${Math.min(start+25,table.rows.length)} din ${table.rows.length}</span>${table.rows.length>25?`<button type="button" class="secondary-button" data-source-page="-1" data-source-mode="${mode}" ${page===0?'disabled':''}>Înapoi</button><button type="button" class="secondary-button" data-source-page="1" data-source-mode="${mode}" ${start+25>=table.rows.length?'disabled':''}>Mai multe rânduri</button>`:''}<button type="button" class="text-button" data-source-standard="${mode}">Folosește formularul standard</button></div>`;
  colorKm(mode);
 }
 function repairFune(table){
  if(Number.isInteger(table.columns.bar))return table;
  const names=['stoc fune','stoc funie','stoc funii','stoc bara','stoc fune bara','stoc funie bara','stoc funii bara'];
  const candidates=table.rows[table.header].map((h,i)=>names.includes(String(h).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim().replace(/ km$/,''))?i:-1).filter(i=>i>=0);
  if(candidates.length===1&&!Object.values(table.columns).includes(candidates[0]))table.columns.bar=candidates[0];return table;
 }
 function set(data){if(data.sourceTable)tables.set(data.mode,data.mode==='plan'?repairFune(clone(data.sourceTable)):clone(data.sourceTable));else tables.delete(data.mode);pages.set(data.mode,0);queueMicrotask(()=>render(data.mode));}
 function clear(mode){tables.delete(mode);render(mode);}
 document.addEventListener('input',e=>{const n=e.target;if(!n.matches('[data-source-row]'))return;const mode=n.dataset.sourceMode,t=tables.get(mode),r=Number(n.dataset.sourceRow),c=Number(n.dataset.sourceCol);while(t.rows[r].length<=c)t.rows[r].push('');t.rows[r][c]=n.value;colorKm(mode);window.PLUPUI.markDirty(mode);window.PLUPSmart?.changed(mode);});
 document.addEventListener('click',e=>{const n=e.target.closest('button');if(!n)return;if(n.dataset.sourcePage){const mode=n.dataset.sourceMode;pages.set(mode,(pages.get(mode)||0)+Number(n.dataset.sourcePage));render(mode);}if(n.dataset.sourceStandard){const mode=n.dataset.sourceStandard;if(!confirm('Treci la șablonul standard? Coloanele suplimentare și totalurile originale nu vor mai apărea în acest raport. Rapoartele salvate se păstrează.'))return;const c=controller(mode),draft=c.draft(),p=attach(draft.payload);delete p.sourceTable;c.restoreDraft({...draft,payload:p});window.PLUPUI.markDirty(mode);window.PLUPSmart?.changed(mode);}});
 document.addEventListener('change',e=>{if(e.target.matches('#report-date,#plan-date,#forecast-date')){const mode=e.target.id==='plan-date'?'plan':e.target.id==='forecast-date'?'forecast':window.PLUPReport.payload().mode;if(tables.has(mode))render(mode);}});
 window.PLUPSource={weekFor,attach,set,clear,render,addForecastWork(){const mode='forecast',t=tables.get(mode);if(!t)return;const additions=[['order','Ordine de execuție'],['priority','Prioritate'],['drumLength','Metri pe tambur']].filter(([k])=>!Number.isInteger(t.columns[k]));const width=Math.max(...t.rows.map(r=>r.length));if(width+additions.length>40)throw Error('Tabelul depășește 40 de coloane.');for(const [i,[key,label]] of additions.entries()){const col=width+i;t.columns[key]=col;while(t.rows[t.header].length<=col)t.rows[t.header].push('');t.rows[t.header][col]=label;for(const [j,rec] of t.records.entries()){while(t.rows[rec.row].length<=col)t.rows[rec.row].push('');t.rows[rec.row][col]=key==='order'?String(j+1):key==='priority'?'normal':'';}}render(mode);window.PLUPUI.markDirty(mode);window.PLUPSmart?.changed(mode);},has:mode=>tables.has(mode)};
})();
