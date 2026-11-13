import { createRoot } from 'react-dom/client'
import { setNonce } from 'get-nonce'
import App from './App'
import './tokens.css'
import './live.css'
import './workspace-finish.css'
import './team.css'

const nonce=document.querySelector<HTMLMetaElement>('meta[name="plup-style-nonce"]')?.content
if(nonce)setNonce(nonce)
function mount(){
  if(!window.PLUPDashboard)return
  const root=document.createElement('div');root.id='plup-modern-root';document.body.append(root)
  createRoot(root).render(<App />)
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true})
else queueMicrotask(mount)
