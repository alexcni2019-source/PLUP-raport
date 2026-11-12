export type View = 'dashboard'|'weekday'|'weekend'|'plan'|'forecast'|'history'
export type Payload = { mode: string; date: string; week?: string; values?: Record<string,Record<string,string>>; rows?: Record<string,string>[] }
type Controller = { payload:()=>Payload; draft:()=>{payload:Payload;metadata:{id?:string|null}} }
declare global {
  interface Window {
    PLUPDashboard:{show:(view:View)=>void;current:()=>View;refreshHistory:()=>Promise<void>}
    PLUPReport:Controller
    PLUPPlan:Controller
    PLUPForecast:Controller
    PLUPTheme:{current:()=>string}
  }
}
export const byId=(id:string)=>document.getElementById(id)
export const fmt=(value:number,digits=2)=>new Intl.NumberFormat('ro-RO',{maximumFractionDigits:digits}).format(value)
export const percentage=(value:number)=>new Intl.NumberFormat('ro-RO',{minimumFractionDigits:1,maximumFractionDigits:1}).format(value)+'%'
export const number=(value:unknown)=>{const n=Number(String(value??'').trim().replace(',','.'));return Number.isFinite(n)&&n>=0?n:0}
export const isProduction=(view:View)=>view==='weekday'||view==='weekend'
export const controller=(view:View)=>view==='plan'?window.PLUPPlan:view==='forecast'?window.PLUPForecast:window.PLUPReport
export const actions=(view:View)=>view==='plan'?{save:'save-plan',render:'image-plan',status:'plan-status'}:view==='forecast'?{save:'forecast-save',render:'forecast-image',status:'forecast-status'}:{save:'save-report-button',render:'generate-report-image',status:'api-status'}
export function snapshot(){
  const view=window.PLUPDashboard.current(),payload=controller(view)?.payload(),ids=actions(view)
  const invalid=!!document.querySelector('input[aria-invalid="true"]')
  const save=byId(ids.save) as HTMLButtonElement|null,render=byId(ids.render) as HTMLButtonElement|null
  const dirty=byId('workspace-state-'+(view==='plan'?'plan':view==='forecast'?'forecast':'report'))?.textContent||''
  return {view,payload,invalid,theme:window.PLUPTheme.current(),saveBusy:!!save?.disabled,renderBusy:!!render?.disabled,status:byId(ids.status)?.textContent||dirty}
}
export function totals(payload:Payload|undefined){
  if(!payload)return {al:0,cu:0,handed:0,backlog:0,waste:0,processed:0,percent:0}
  if(payload.rows){
    const key=payload.mode==='plan'?'planned':'tons'
    const al=payload.rows.filter(r=>r.material==='AL').reduce((n,r)=>n+number(r[key]),0)
    const cu=payload.rows.filter(r=>r.material==='CU').reduce((n,r)=>n+number(r[key]),0)
    return {al,cu,handed:al+cu,backlog:0,waste:0,processed:0,percent:0}
  }
  const rows=Object.values(payload.values||{}),sum=(key:string)=>rows.reduce((n,r)=>n+number(r[key]),0)
  const al=sum('al'),cu=sum('cu'),handed=al+cu,backlog=sum('backlogAl')+sum('backlogCu'),waste=sum('wasteAl')+sum('wasteCu'),processed=handed+waste
  return {al,cu,handed,backlog,waste,processed,percent:processed?waste/processed*100:0}
}
export function click(id:string){(byId(id) as HTMLButtonElement|null)?.click()}
