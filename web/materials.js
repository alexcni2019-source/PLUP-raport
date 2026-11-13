/* Keep the section rules in sync with server/materials.py. No product-name inference. */
(() => {
  'use strict';
  const normalize=value=>String(value??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  function marker(value,subtotal=false){
    value=normalize(value);
    if(subtotal){if(!value.startsWith('total '))return null;value=value.slice(6);}
    else if(value.startsWith('total '))return null;
    value=value.replace(/^(?:material|metal|produse|sectiune|rubrica)\s+/,'').replace(/\s+(?:tone|tona|t|km)$/,'');
    if(['al','aluminiu','aluminium','al aluminiu','aluminiu al'].includes(value))return 'AL';
    if(['cu','cupru','copper','cu cupru','cupru cu'].includes(value))return 'CU';
    return null;
  }
  function rowMarker(row,columns,isRecord=false){
    if(Number.isInteger(columns.material)&&marker(row[columns.material]))return marker(row[columns.material]);
    const populated=row.filter(cell=>String(cell??'').trim());
    if(populated.length===1)return marker(populated[0]);
    const used=Object.values(columns),product=columns.product??row.length;
    for(let i=0;i<product;i++)if(!used.includes(i)&&marker(row[i]))return marker(row[i]);
    if(!isRecord){const labels=new Set(row.map(cell=>marker(cell)).filter(Boolean));if(labels.size===1&&row.every(cell=>!String(cell??'').trim()||marker(cell)))return [...labels][0];}
    return null;
  }
  function classify(table,useFallback=true){
    const records=new Map(table.records.map(record=>[record.row,record]));
    const result=new Map();let pending=[],context=null;
    function finish(subtotal=null){
      for(const [row,explicit] of pending){
        if(explicit&&subtotal&&explicit!==subtotal)throw Error(`Rândul ${row+1}: materialul contrazice subtotalul ${subtotal}. Verifică rubrica din tabel.`);
        result.set(row,explicit||subtotal||(useFallback?records.get(row).material:null));
      }
      pending=[];
    }
    table.rows.forEach((row,i)=>{
      if(i<=table.header)return;
      const totals=[...new Set(row.map(cell=>marker(cell,true)).filter(Boolean))];
      if(totals.length>1)throw Error(`Rândul ${i+1}: subtotal de material ambiguu.`);
      if(totals.length){finish(totals[0]);context=null;return;}
      const material=rowMarker(row,table.columns,records.has(i));
      if(material&&material!==context){finish();context=material;}
      if(records.has(i))pending.push([i,material||context]);
    });
    finish();return result;
  }
  window.PLUPMaterials={marker,rowMarker,classify};
})();
