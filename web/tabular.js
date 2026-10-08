(() => {
 'use strict';
 const $=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const configs={forecast:[['material','Material'],['product','Produs'],['km','KM'],['tons','Tone'],['client','Client'],['measure','Măsurări'],['status','Stadiu'],['notes','Observații']],plan:[['material','Material'],['client','Client'],['product','Produs'],['planned','Metal planificat'],['handed','Metal predat'],['wire','Sârmă'],['spool','Stoc lită'],['bar','Stoc fune / bară'],['vane','Stoc vane'],['cable','Stoc cablat'],['mi','Stoc M.I.'],['armored','Stoc armat'],['mf','Stoc M.F.'],['goods','Marfă predată'],['notes','Observații']],report:[['date','Data'],['al','Aluminiu predat'],['cu','Cupru predat'],['backlogAl','Backlog aluminiu'],['backlogCu','Backlog cupru'],['wasteAl','Deșeu aluminiu'],['wasteCu','Deșeu cupru'],['op_asumreal','Asumat / realizat'],['op_status','Realizat vs status'],['op_plan','Realizat vs plan'],['op_previz','Previz schimb 1'],['op_backal','Backlog AL operațional'],['op_backcu','Backlog CU operațional'],['op_rigid1','SF Rigid 1'],['op_rigid2','SF Rigid 2'],['op_rigid3','SF Rigid 3'],['op_multi1','SF Multifir 1'],['op_multi2','SF Multifir 2'],['op_niehoff','SF Niehoff'],['op_beta3','SF Beta 3'],['op_stocal','Stoc AL'],['op_stoccu','Stoc CU'],['obs','Observații']]};
 const aliases={material:['material','metal','al cu'],product:['produs','produse','product'],client:['client','beneficiar'],km:['km','kilometri','cantitate km'],tons:['tone','tona','t','cantitate tone'],measure:['masurari','masurare','lungimi'],status:['stadiu','status'],notes:['observatii','obs'],planned:['metal planificat','planificat','plan tone'],handed:['metal predat','predat tone'],wire:['sarma'],spool:['stoc lita','lita'],bar:['stoc fune','stoc bara','stoc fune bara'],vane:['stoc vane'],cable:['stoc cablat'],mi:['stoc m i'],armored:['stoc armati','stoc armat'],mf:['stoc m f'],goods:['marfa predata','km predati'],date:['data','zi','date'],al:['aluminiu predat','predat al','al predat','aluminiu','al'],cu:['cupru predat','predat cu','cu predat','cupru','cu'],backlogAl:['backlog aluminiu','backlog al'],backlogCu:['backlog cupru','backlog cu'],wasteAl:['deseu aluminiu','deseu al'],wasteCu:['deseu cupru','deseu cu'],obs:['observatii','obs']};
 const norm=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
 const profileKey=(suffix,headers)=>'plup-columns-v1-'+suffix+'-'+JSON.stringify(headers.map(norm));
 const profile=(suffix,headers)=>{try{return JSON.parse(localStorage.getItem(profileKey(suffix,headers))||'null');}catch{return null;}};
 const state=new Map();const modeFor=s=>s==='report'?window.PLUPReport.payload().mode:s,ctrl=s=>s==='report'?window.PLUPReport:s==='plan'?window.PLUPPlan:window.PLUPForecast;
 for(const [root,suffix] of [['report-view','report'],['plan-view','plan'],['forecast-view','forecast']]){
  const panel=document.createElement('details');panel.className='smart-excel';panel.open=true;panel.innerHTML=`<summary>Import rapid din Excel / tabel</summary><p class="smart-note">Copiază celulele cu antet din Excel și lipește-le aici, sau încarcă .xlsx / .csv. Valorile sunt citite direct; verifici coloanele înainte de aplicare.</p><label>Tabel copiat<textarea id="excel-paste-${suffix}" rows="3" placeholder="Lipește aici celulele copiate din Excel (Ctrl+V / Lipește)."></textarea></label><div class="plan-actions"><button class="text-button" type="button" data-template="${suffix}">Copiază antetul pentru Excel</button><button class="secondary-button" type="button" data-read-table="${suffix}">Citește tabelul lipit</button><label class="plan-file-button">Încarcă Excel / CSV<input id="excel-file-${suffix}" type="file" accept=".xlsx,.csv,.tsv,text/csv" hidden></label></div><p id="excel-status-${suffix}" role="status"></p><div id="excel-preview-${suffix}" hidden></div>`;const container=$(root).querySelector(root==='report-view'?'.editor':'.plan-panel');container.querySelector('.panel-head').after(panel);
  $('excel-file-'+suffix).addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>6000000)throw Error('Fișierul depășește 6 MB. Copiază doar tabelul necesar.');let body;if(/\.(csv|tsv)$/i.test(file.name))body={text:await file.text()};else body={file:await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=reject;r.readAsDataURL(file);})};await read(suffix,body);}catch(error){$('excel-status-'+suffix).textContent=error.message;}finally{e.target.value='';}});
 }
 async function read(suffix,body){const node=$('excel-status-'+suffix);node.textContent='Se citesc celulele…';try{const response=await window.PLUPFetch('/api/smart/table',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(body)}),data=await response.json();if(!response.ok)throw Error(data.error||'Tabel invalid.');state.set(suffix,{data,sheet:0,header:0});draw(suffix,true);node.textContent=data.message;}catch(e){node.textContent=e.message;}}
 function score(headers,fields){return fields.reduce((n,[key,label])=>n+headers.filter(h=>match(h,key,label)).length,0);}
 function match(value,key,label){const n=norm(value);return [...(aliases[key]||[]),norm(label)].some(a=>n===a||n===a+' t'||n===a+' tone'||n===a+' km');}
 function draw(suffix,detect=false){const st=state.get(suffix),sheet=st.data.sheets[st.sheet],fields=configs[suffix];if(detect){let best=-1;sheet.rows.slice(0,15).forEach((r,i)=>{const scoreNow=score(r,fields)+(profile(suffix,r)?100:0);if(scoreNow>best){best=scoreNow;st.header=i;}});}const headers=sheet.rows[st.header]||[],savedMapping=profile(suffix,headers),width=Math.max(...sheet.rows.map(r=>r.length));const node=$('excel-preview-'+suffix);node.hidden=false;
  node.innerHTML=`<div class="smart-heading"><label>Foaie<select data-sheet="${suffix}">${st.data.sheets.map((s,i)=>`<option value="${i}" ${i===st.sheet?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label><label>Rândul cu antet<input data-header="${suffix}" type="number" min="1" max="${sheet.rows.length}" value="${st.header+1}"></label></div><p class="smart-note">${savedMapping?'Asocierea memorată pentru acest antet a fost reaplicată. ':''}Asocierile de mai jos sunt folosite pentru calcule. Tabelul complet păstrează inclusiv coloanele fără asociere.</p><label class="forecast-status-option"><input id="excel-keep-source-${suffix}" type="checkbox" checked>Păstrează tabelul complet: toate antetele, coloanele, rândurile și totalurile, în ordinea din Excel.</label><details><summary>Asocieri pentru calcule și diagrame</summary><div class="excel-mapping">${fields.map(([key,label])=>{const candidates=headers.map((h,i)=>match(h,key,label)?i:-1).filter(i=>i>=0);const selected=Number.isInteger(savedMapping?.[key])&&savedMapping[key]>=-1&&savedMapping[key]<width?savedMapping[key]:candidates.length===1?candidates[0]:-1;return `<label>${esc(label)}<select data-map="${key}"><option value="-1">Necompletat</option>${Array.from({length:width},(_,i)=>`<option value="${i}" ${selected===i?'selected':''}>${i+1}: ${esc(headers[i]||'Fără antet')}</option>`).join('')}</select></label>`;}).join('')}</div></details><p>${esc(sheet.warnings.join(' '))}</p><details open><summary>Previzualizare sursă · ${sheet.rows.length-st.header-1} rânduri după antet</summary><div class="smart-scroll"><table><thead><tr>${Array.from({length:width},(_,i)=>`<th>${esc(headers[i]||'Coloana '+(i+1))}</th>`).join('')}</tr></thead><tbody>${sheet.rows.slice(st.header+1,st.header+11).map(r=>`<tr>${Array.from({length:width},(_,i)=>`<td>${esc(r[i]||'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details><button class="primary-button" type="button" data-apply-table="${suffix}">Aplică tabelul</button><p class="smart-note">Aplicarea înlocuiește datele formularului. Raportul final se salvează separat, după verificare.</p>`;
 }
 const numeric=new Set(['km','tons','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','al','cu','backlogAl','backlogCu','wasteAl','wasteCu']);
 function value(raw,key){let s=String(raw??'').trim();if(s==='—'||s==='-')return '';if(numeric.has(key)){s=s.replace(/\s/g,'').replace(/(?:tone|tona|km|t)$/i,'');}if(s.length>120)throw Error('Un câmp depășește 120 caractere. Scurtează-l în sursă.');return s;}
 function parseDate(s){if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;const m=s.match(/^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})$/);return m?`${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`:null;}
 function apply(suffix){
  const st=state.get(suffix),sheet=st.data.sheets[st.sheet],mapping=Object.fromEntries([...$('excel-preview-'+suffix).querySelectorAll('[data-map]')].map(n=>[n.dataset.map,Number(n.value)]));
  const used=Object.values(mapping).filter(i=>i>=0),keep=$('excel-keep-source-'+suffix).checked;
  if(new Set(used).size!==used.length)throw Error('Aceeași coloană este asociată mai multor câmpuri. Corectează asocierea.');
  const mode=modeFor(suffix),existing=ctrl(suffix).payload(),hasQuantity=['al','cu','backlogAl','backlogCu','wasteAl','wasteCu'].some(k=>mapping[k]>=0);
  if(!keep&&suffix!=='report'&&mapping.product<0)throw Error('Asociază coloana Produs.');
  if(!keep&&suffix==='report'&&!hasQuantity)throw Error('Asociază cel puțin o coloană de cantități.');
  let material='AL';const rows=[],records=[],values={};let reportDate=existing.date;
  const dateMatch=sheet.rows.slice(0,st.header).flat().join(' ').match(/\b(\d{2}[./]\d{2}[./]\d{4})\b/);
  if(dateMatch&&mode!=='weekend')reportDate=parseDate(dateMatch[1])||reportDate;
  for(const [offset,line] of sheet.rows.slice(st.header+1).entries()){
   if(!line.some(v=>String(v??'').trim()))continue;
   const sourceRow=st.header+1+offset,first=norm(line.slice(0,3).join(' '));if(/^(total|intrari|suma)/.test(first))continue;
   if(suffix==='report'){
    if(!hasQuantity)continue;
    const fields=Object.fromEntries(configs.report.filter(([k])=>k!=='date').map(([k])=>[k,value(mapping[k]>=0?line[mapping[k]]:'',k)]));
    if(!Object.values(fields).some(Boolean))continue;
    let day=mapping.date>=0?parseDate(value(line[mapping.date],'date')):reportDate;
    if(!day)throw Error('Data unui rând nu poate fi interpretată. Folosește ZZ.LL.AAAA sau AAAA-LL-ZZ.');
    if(values[day])throw Error('Mai multe rânduri au aceeași zi. Corectează asocierea pentru calcule sau lasă cantitățile neasociate; tabelul complet se păstrează.');
    values[day]=fields;records.push({row:sourceRow,stamp:day});
   }else{
    const token=norm(mapping.material>=0?line[mapping.material]:line[0]);
    if(['al','aluminiu','aluminium'].includes(token))material='AL';if(['cu','cupru','copper'].includes(token))material='CU';
    if(mapping.product<0)continue;
    const row=Object.fromEntries(configs[suffix].filter(([k])=>k!=='material').map(([k])=>[k,value(mapping[k]>=0?line[mapping[k]]:'',k)]));
    if(!row.product){if(!keep&&Object.values(row).some(Boolean)&&!['al','cu','aluminiu','cupru'].includes(token))throw Error('Un rând conține date fără produs. Verifică antetul sau coloana Produs.');continue;}
    if(match(row.product,'product','Produs'))continue;
    rows.push({material,...row});records.push({row:sourceRow,material});
   }
  }
  let payload;
  if(suffix==='report'){
   const dates=Object.keys(values).sort();if(!dates.length&&!keep)throw Error('Nu există rânduri de importat.');
   if(mode==='weekday'&&dates.length>1)throw Error('Raportul zilnic acceptă o singură dată. Alege raportul de 3 zile pentru weekend.');
   if(dates.length)reportDate=dates[0];
   if(mode==='weekend'){
    const d=new Date(reportDate+'T12:00:00');if(d.getDay()!==5)throw Error('Prima zi a raportului de 3 zile trebuie să fie vineri.');
    const allowed=[0,1,2].map(i=>{const x=new Date(d);x.setDate(x.getDate()+i);return x.toLocaleDateString('sv-SE');});
    if(dates.some(d=>!allowed.includes(d)))throw Error('Datele trebuie să fie vineri, sâmbătă și duminică din același weekend.');
   }
   payload={mode,date:reportDate,values};
   records.forEach(r=>{r.day=Math.round((Date.parse(r.stamp+'T12:00:00Z')-Date.parse(reportDate+'T12:00:00Z'))/86400000);delete r.stamp;});
  }else{
   if((!rows.length&&!keep)||rows.length>100)throw Error('Importul poate avea cel mult 100 produse asociate pentru calcule.');
   payload=suffix==='plan'?{...existing,date:reportDate,rows}:{mode,date:reportDate,rows};
   delete payload.sourceTable;
  }
  if(keep)payload.sourceTable={version:1,header:st.header,rows:sheet.rows.map(r=>r.map(v=>String(v??''))),columns:Object.fromEntries(Object.entries(mapping).filter(([,i])=>i>=0)),records,date:reportDate};
  if(!keep){const unmapped=(sheet.rows[st.header]||[]).filter((h,i)=>h&&!used.includes(i));if(unmapped.length&&!confirm('Șablonul standard nu include: '+unmapped.join(', ')+'. Continui fără aceste coloane?'))return;}
  if(!confirm('Aplici tabelul și înlocuiești datele curente? Rapoartele salvate în istoric se păstrează.'))return;
  try{localStorage.setItem(profileKey(suffix,sheet.rows[st.header]||[]),JSON.stringify(mapping));}catch{}
  const review=keep||suffix==='report'?[]:rows.flatMap((r,i)=>Object.keys(r).filter(k=>k!=='material').map(k=>i+':'+k));
  ctrl(suffix).restoreDraft({payload,metadata:{id:null,needsReview:!keep&&suffix!=='report',review}});
  window.PLUPUI.markDirty(mode);window.PLUPSmart.clearImport(mode);window.PLUPSmart.changed(mode);
  $('excel-status-'+suffix).textContent=keep?'Tabelul complet este păstrat. Verifică celulele de mai jos, apoi salvează sau generează PNG.':'Date aplicate în șablonul standard. Verifică înainte de generare.';
 }
 document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.template){const suffix=b.dataset.template,fields=suffix==='report'?configs.report.slice(0,7):configs[suffix],text=fields.map(([,label])=>label).join('\t');try{await navigator.clipboard.writeText(text);$('excel-status-'+suffix).textContent='Antet copiat. Lipește-l în Excel și completează rândurile sub el.';}catch{$('excel-paste-'+suffix).value=text;$('excel-paste-'+suffix).focus();$('excel-paste-'+suffix).select();$('excel-status-'+suffix).textContent='Antet selectat. Copiază-l și lipește-l în Excel.';}}if(b.dataset.readTable)await read(b.dataset.readTable,{text:$('excel-paste-'+b.dataset.readTable).value});if(b.dataset.applyTable){try{apply(b.dataset.applyTable);}catch(error){$('excel-status-'+b.dataset.applyTable).textContent=error.message;}}});
 document.addEventListener('change',e=>{if(e.target.dataset.sheet){const suffix=e.target.dataset.sheet;state.get(suffix).sheet=Number(e.target.value);draw(suffix,true);}if(e.target.dataset.header){const suffix=e.target.dataset.header,st=state.get(suffix);st.header=Math.min(Math.max(0,Number(e.target.value)-1),st.data.sheets[st.sheet].rows.length-1);draw(suffix);}});
 document.addEventListener('paste',e=>{const text=e.clipboardData?.getData('text/plain');if(!text||!text.includes('\t'))return;const mode=window.PLUPDashboard.current();if(!['plan','forecast','weekday','weekend'].includes(mode))return;const suffix=['weekday','weekend'].includes(mode)?'report':mode;e.preventDefault();e.stopImmediatePropagation();$('excel-paste-'+suffix).value=text;void read(suffix,{text});},true);
})();
