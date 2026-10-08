(() => {
 'use strict';
 const tables=new Map(),pages=new Map(),$=id=>document.getElementById(id);
 const clone=x=>JSON.parse(JSON.stringify(x));
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const suffix=mode=>['weekday','weekend'].includes(mode)?'report':mode;
 const controller=mode=>mode==='plan'?window.PLUPPlan:mode==='forecast'?window.PLUPForecast:window.PLUPReport;
 const fields={plan:['material','client','product','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','notes'],forecast:['material','product','km','tons','client','measure','status','notes'],report:['al','cu','backlogAl','backlogCu','wasteAl','wasteCu','op_asumreal','op_status','op_plan','op_previz','op_backal','op_backcu','op_rigid1','op_rigid2','op_rigid3','op_multi1','op_multi2','op_niehoff','op_beta3','op_stocal','op_stoccu','obs']};
 const numeric=new Set(['km','tons','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','al','cu','backlogAl','backlogCu','wasteAl','wasteCu']);
 const convert=(v,k)=>{let s=String(v??'').trim();if(s==='—'||s==='-')return '';if(numeric.has(k))s=s.replace(/\s/g,'').replace(/(?:tone|tona|km|t)$/i,'');return s;};
 const day=(stamp,n)=>{const d=new Date(stamp+'T12:00:00');d.setDate(d.getDate()+n);return d.toLocaleDateString('sv-SE');};
 function attach(base){
  const source=tables.get(base.mode);if(!source)return base;
  const table=clone(source),cols=table.columns,type=suffix(base.mode);
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
 }
 function set(data){if(data.sourceTable)tables.set(data.mode,clone(data.sourceTable));else tables.delete(data.mode);pages.set(data.mode,0);queueMicrotask(()=>render(data.mode));}
 function clear(mode){tables.delete(mode);render(mode);}
 document.addEventListener('input',e=>{const n=e.target;if(!n.matches('[data-source-row]'))return;const mode=n.dataset.sourceMode,t=tables.get(mode),r=Number(n.dataset.sourceRow),c=Number(n.dataset.sourceCol);while(t.rows[r].length<=c)t.rows[r].push('');t.rows[r][c]=n.value;window.PLUPUI.markDirty(mode);window.PLUPSmart?.changed(mode);});
 document.addEventListener('click',e=>{const n=e.target.closest('button');if(!n)return;if(n.dataset.sourcePage){const mode=n.dataset.sourceMode;pages.set(mode,(pages.get(mode)||0)+Number(n.dataset.sourcePage));render(mode);}if(n.dataset.sourceStandard){const mode=n.dataset.sourceStandard;if(!confirm('Treci la șablonul standard? Coloanele suplimentare și totalurile originale nu vor mai apărea în acest raport. Rapoartele salvate se păstrează.'))return;const c=controller(mode),draft=c.draft(),p=attach(draft.payload);delete p.sourceTable;c.restoreDraft({...draft,payload:p});window.PLUPUI.markDirty(mode);window.PLUPSmart?.changed(mode);}});
 document.addEventListener('change',e=>{if(e.target.matches('#report-date,#plan-date,#forecast-date')){const mode=e.target.id==='plan-date'?'plan':e.target.id==='forecast-date'?'forecast':window.PLUPReport.payload().mode;if(tables.has(mode))render(mode);}});
 window.PLUPSource={attach,set,clear,render,has:mode=>tables.has(mode)};
})();
