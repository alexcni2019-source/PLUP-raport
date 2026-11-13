import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Activity, CalendarDays, Check, CheckCircle2, ChevronRight, Factory, FileImage, History, Home, LogOut, Menu, Moon, ShieldCheck, Sun, Table2, TrendingUp } from 'lucide-react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { TooltipProvider } from '@/components/ui/tooltip'
import { actions, byId, click, controller, fmt, isProduction, percentage, snapshot, totals } from './bridge'
import type { Payload, View } from './bridge'

const navigation: {id:View;label:string;icon:typeof Home}[]=[{id:'dashboard',label:'Acasă',icon:Home},{id:'weekday',label:'Producție',icon:Factory},{id:'plan',label:'Plan',icon:Table2},{id:'forecast',label:'Previz',icon:TrendingUp},{id:'history',label:'Istoric',icon:History}]
const titles:Record<View,[string,string]>={dashboard:['Spațiul tău de lucru','Rapoarte, producție și planificare.'],weekday:['Raport de producție','Completează și verifică separat valorile pentru aluminiu și cupru.'],weekend:['Raport pentru trei zile','Vineri, sâmbătă și duminică, cu totalul perioadei.'],plan:['Plan de producție','Produse, clienți și stadii, separate pe material.'],forecast:['Previz zilnic','Cantități, clienți și stadii de producție.'],history:['Istoric rapoarte','Deschide, corectează și regenerează rapoartele salvate.']}
const legacyIds=['dashboard-view','report-toolbar','production-summary','report-view','plan-view','forecast-view','history-view']

function useLiveState(){
  const [state,setState]=useState(snapshot)
  useEffect(()=>{
    let frame=0
    const update=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>setState(snapshot()))}
    const events=['plup:view','plup:state','plup:drafts','plup:home','plup:import','input','change']
    events.forEach(event=>document.addEventListener(event,update))
    const observer=new MutationObserver(update)
    legacyIds.forEach(id=>{const node=byId(id);if(node)observer.observe(node,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['disabled','aria-invalid','hidden']})})
    const appearance=new MutationObserver(update);appearance.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']})
    update();return()=>{cancelAnimationFrame(frame);observer.disconnect();appearance.disconnect();events.forEach(event=>document.removeEventListener(event,update))}
  },[])
  return state
}

function LegacyViews(){
  const ref=useRef<HTMLDivElement>(null)
  useLayoutEffect(()=>{legacyIds.forEach(id=>{const node=byId(id);if(node)ref.current!.append(node)})},[])
  return <div className="working-views" ref={ref}/>
}

function Summary({payload,invalid,pending}:{payload:Payload;invalid:boolean;pending:boolean}){
  const t=totals(payload)
  const metrics=payload.rows?[
    {label:'Aluminiu · AL',value:t.al,note:payload.mode==='plan'?'Metal planificat':'Cantitate previzionată'},
    {label:'Cupru · CU',value:t.cu,note:payload.mode==='plan'?'Metal planificat':'Cantitate previzionată'},
    {label:'Total AL + CU',value:t.handed,note:'Materiale separate'},
  ]:[
    {label:'Total predat',value:t.handed,note:`AL ${fmt(t.al)} t · CU ${fmt(t.cu)} t`},
    {label:'Backlog',value:t.backlog,note:'Separat de materialul procesat'},
    {label:'Total procesat',value:t.processed,note:`Deșeu ${fmt(t.waste)} t · ${percentage(t.percent)}`},
  ]
  return <section className="workspace-summary" aria-label="Indicatorii raportului">{metrics.map(({label,value,note})=><div key={label} className="workspace-summary-item"><span>{label}</span><strong>{invalid||pending?'—':fmt(value)} <small>t</small></strong><p>{pending?'Import neaplicat':invalid?'Verifică valorile':note}</p></div>)}</section>
}

function Review({payload,invalid,pending}:{payload:Payload;invalid:boolean;pending:boolean}){
  const t=totals(payload)
  return <Dialog><DialogTrigger asChild><Button variant="outline" disabled={pending}><CheckCircle2/>Verifică datele</Button></DialogTrigger><DialogContent className="live-review"><DialogHeader><DialogTitle>Verifică raportul</DialogTitle><DialogDescription>{payload.date} · {payload.mode==='weekend'?'Trei zile':payload.mode==='plan'?'Plan de producție':payload.mode==='forecast'?'Previz zilnic':'Producție zilnică'}</DialogDescription></DialogHeader>{invalid?<p role="alert">Corectează valorile marcate înainte de salvare sau export.</p>:<><div className="review-materials"><div><Badge>AL · Aluminiu</Badge><strong>{fmt(t.al)} t</strong></div><div><Badge className="cu">CU · Cupru</Badge><strong>{fmt(t.cu)} t</strong></div></div><dl><div><dt>{payload.rows?'Total general':'Total predat'}</dt><dd>{fmt(t.handed)} t</dd></div>{!payload.rows&&<><div><dt>Backlog</dt><dd>{fmt(t.backlog)} t</dd></div><div><dt>Total procesat</dt><dd>{fmt(t.processed)} t</dd></div><div><dt>Deșeu / procesat</dt><dd>{percentage(t.percent)}</dd></div></>}</dl><p className="hint">Verifică și câmpurile detaliate din raport înainte de salvare sau export.</p></>}</DialogContent></Dialog>
}

export default function App(){
  const state=useLiveState(),{view,payload,theme}=state,[menuOpen,setMenuOpen]=useState(false)
  const title=useRef<HTMLHeadingElement>(null),pointer=useRef<number>(0)
  const production=isProduction(view),editing=production||view==='plan'||view==='forecast',ids=actions(view)
  useLayoutEffect(()=>{document.body.classList.add('plup-modern');document.documentElement.dataset.finish='on'},[])
  useEffect(()=>{document.documentElement.classList.toggle('dark',theme==='dark')},[theme])
  useEffect(()=>{title.current?.focus({preventScroll:true})},[view])
  useEffect(()=>()=>cancelAnimationFrame(pointer.current),[])
  const navigate=(id:View)=>{window.PLUPDashboard.show(id);setMenuOpen(false)}
  const nav=<nav aria-label="Module PLUP">{navigation.map(({id,label,icon:Icon})=><Button key={id} variant="ghost" aria-current={(view===id||(id==='weekday'&&production))?'page':undefined} onClick={()=>navigate(id)}><Icon size={22}/><span>{label}</span></Button>)}</nav>
  const track=(event:ReactPointerEvent<HTMLElement>)=>{
    if(!matchMedia('(hover:hover) and (pointer:fine)').matches||matchMedia('(prefers-reduced-motion:reduce)').matches)return
    const target=event.target instanceof Element?event.target.closest<HTMLElement>('.modern-metric,.production-material'):null
    if(!target)return
    const {clientX,clientY}=event;cancelAnimationFrame(pointer.current)
    pointer.current=requestAnimationFrame(()=>{const rect=target.getBoundingClientRect();target.style.setProperty('--pointer-x',`${clientX-rect.left}px`);target.style.setProperty('--pointer-y',`${clientY-rect.top}px`)})
  }
  return <TooltipProvider delayDuration={80}><a className="modern-skip" href="#modern-main">Mergi la conținut</a><div className="modern-shell"><aside className="modern-sidebar"><a className="modern-brand" href="/" onClick={e=>{e.preventDefault();navigate('dashboard')}}><b>NRG<small>CABLES</small></b><span>PLUP</span></a>{nav}<div className="modern-private"><ShieldCheck size={20}/><span>Acces privat</span></div></aside><div className="modern-body"><header className="modern-topbar"><div className="modern-mobile-nav"><Sheet open={menuOpen} onOpenChange={setMenuOpen}><SheetTrigger asChild><Button variant="ghost" size="icon" data-ui-safe aria-label="Deschide navigarea"><Menu/></Button></SheetTrigger><SheetContent side="left" className="live-nav-sheet"><SheetHeader><SheetTitle>NRG Cables · PLUP</SheetTitle><SheetDescription>Alege fluxul de lucru.</SheetDescription></SheetHeader>{nav}</SheetContent></Sheet></div><span className="modern-breadcrumb"><b>NRG Cables</b><ChevronRight size={15}/><span>PLUP</span></span><div className="modern-appearance"><Label htmlFor="modern-theme" data-ui-safe>{theme==='dark'?<Moon size={18}/>:<Sun size={18}/>}<span>Întunecat</span><Switch data-ui-safe id="modern-theme" aria-label="Temă întunecată" checked={theme==='dark'} onCheckedChange={()=>click('theme-toggle')}/></Label><Button variant="ghost" data-ui-safe onClick={()=>click('theme-system')} className="auto-theme">Auto</Button>{byId('identity-logout')&&<Button variant="ghost" size="icon" data-ui-safe onClick={()=>click('identity-logout')} aria-label="Deconectare"><LogOut size={18}/></Button>}</div></header><main id="modern-main" className={`modern-main${editing?' editing-workspace':''}`} onPointerMove={track}><div className="modern-context"><span><Home size={15}/><ChevronRight size={13}/>{navigation.find(n=>n.id===view)?.label||(production?'Producție':'PLUP')}</span>{editing&&<Badge variant="outline" className="modern-save-badge"><span/>{state.pendingImport?'Import neaplicat':controller(view).draft().metadata.id?'Raport din istoric':'Ciornă de lucru'}</Badge>}</div><div className="modern-heading"><div><h1 ref={title} tabIndex={-1}>{titles[view][0]}</h1><p>{titles[view][1]}</p></div><div className="modern-heading-tools">{editing&&payload&&<><span className="modern-date"><CalendarDays size={17}/>{payload.date.split('-').reverse().join('.')}</span><div className="modern-actions"><Review payload={payload} invalid={state.invalid} pending={state.pendingImport}/><Button variant="outline" disabled={state.renderBusy||state.pendingImport} aria-busy={state.renderBusy} onClick={()=>click(ids.render)}><FileImage/>{state.renderBusy?'Se generează…':'Generează PNG'}</Button><Button disabled={state.saveBusy||state.pendingImport} aria-busy={state.saveBusy} onClick={()=>click(ids.save)}><Check/>{state.saveBusy?'Se salvează…':'Salvează în istoric'}</Button></div></>}{view==='history'&&<Button variant="outline" onClick={()=>click('refresh-history')}><History/>Reîncarcă istoricul</Button>}</div></div>{editing&&payload&&<><Summary payload={payload} invalid={state.invalid} pending={state.pendingImport}/><p className="modern-status" role="status">{state.status}</p></>}<LegacyViews/><footer className="modern-footer"><span>NRG Cables · PLUP</span><span><Activity size={14}/>Rapoarte interne de producție</span></footer></main></div></div></TooltipProvider>
}
