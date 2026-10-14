(() => {
  'use strict';
  window.PLUPSplitExport=async ({payload,current,valid,theme,showStatus=true,target})=>{
    const snapshot=JSON.stringify(payload),parts=payload.mode==='forecast'
      ?[['summary','Execuție și diagrame'],['table','Lista de previz']]
      :[['summary','Analiză și diagrame'],['table','Lista produselor']];
    if(payload.mode==='plan'){
      const response=await window.PLUPFetch('/api/plan/analysis',{method:'POST',headers:{'Content-Type':'application/json'},body:snapshot,credentials:'same-origin'});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Analiza fluxului nu a reușit.');
      for(const item of data.flow_pages||[])parts.push(['clients','Flux · '+item.client+' · pagina '+(item.page+1),item.page]);
    }
    const blobs=[];
    for(const [section,title,page=0] of parts){
      const response=await window.PLUPFetch(`/api/render?theme=${theme}&status=${showStatus?'1':'0'}&section=${section}&page=${page}`,{method:'POST',headers:{'Content-Type':'application/json'},body:snapshot,credentials:'same-origin'});
      if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'Generarea nu a reușit.');}
      const blob=await response.blob();
      if(!valid())return false;
      if(JSON.stringify(current())!==snapshot)throw Error('Datele au fost schimbate în timpul generării. Generează din nou imaginile.');
      if(blob.type!=='image/png')throw Error('Răspuns imagine invalid.');
      blobs.push({section,title,blob,page});
    }
    const fragment=document.createDocumentFragment(),urls=[];
    try{
      for(const {section,title,blob,page} of blobs){
        const url=URL.createObjectURL(blob);urls.push(url);
        const wrap=document.createElement('div'),heading=document.createElement('h3'),img=document.createElement('img'),link=document.createElement('a');
        wrap.className='image-result';heading.textContent=title;img.src=url;img.alt=title+' PLUP';link.href=url;
        link.download=`NRG_PLUP_${payload.mode}_${payload.date}_${section}_${page+1}_${payload.mode==='forecast'?(showStatus?'productie':'directiune')+'_':''}${theme}.png`;
        link.textContent=`Descarcă PNG · ${title} ↓`;wrap.append(heading,img,link);fragment.append(wrap);
      }
      window.PLUPUI.clearImages(target);target.replaceChildren(fragment);
    }catch(error){urls.forEach(URL.revokeObjectURL);throw error;}
    return true;
  };
})();
