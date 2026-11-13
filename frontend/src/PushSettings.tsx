import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { Button } from '@/components/ui/button'

const api = '/api/admin/push'
const supported = typeof window !== 'undefined' && 'Notification' in window &&
  'serviceWorker' in navigator && 'PushManager' in window

async function request<T>(body?: object): Promise<T> {
  const response = await window.PLUPFetch(api, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : {})
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || 'Notificările sunt momentan indisponibile.')
  return result
}

export default function PushSettings() {
  const [key, setKey] = useState('')
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null)
  const [active, setActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    if (!supported) return
    let mounted = true
    async function initialize() {
      try {
        const [settings] = await Promise.all([
          request<{ publicKey: string }>(),
          navigator.serviceWorker.register('/push-worker.js'),
        ])
        const worker = await navigator.serviceWorker.ready
        const subscription = await worker.pushManager.getSubscription()
        const result = subscription
          ? await request<{ active: boolean }>({ action: 'status', endpoint: subscription.endpoint })
          : { active: false }
        if (!mounted) return
        setKey(settings.publicKey)
        setRegistration(worker)
        setActive(result.active)
      } catch (error) {
        if (mounted) setStatus((error as Error).message)
      }
    }
    void initialize()
    return () => { mounted = false }
  }, [])

  async function change(action: 'enable' | 'disable' | 'test') {
    if (!registration || busy) return
    setBusy(true)
    setStatus('')
    try {
      if (action === 'enable' && Notification.permission !== 'granted') {
        const permission = await Notification.requestPermission()
        if (permission !== 'granted') {
          throw new Error('Permite notificările din setările site-ului, apoi încearcă din nou.')
        }
      }
      const existing = await registration.pushManager.getSubscription()
      if (action === 'enable') {
        const subscription = existing || await registration.pushManager.subscribe({
          userVisibleOnly: true, applicationServerKey: key,
        })
        await request({ action, ...subscription.toJSON() })
        setActive(true)
        setStatus('Notificările sunt active pe acest dispozitiv.')
      } else if (existing) {
        const result = await request<{ queued?: boolean }>({ action, endpoint: existing.endpoint })
        if (action === 'disable') {
          setActive(false)
          await existing.unsubscribe()
          setStatus('Notificările au fost dezactivate pe acest dispozitiv.')
        } else if (result.queued) {
          setStatus('Notificarea de test a fost pusă în coadă.')
        } else {
          setStatus('Testul nu a putut fi programat. Încearcă din nou.')
        }
      } else {
        setActive(false)
        setStatus('Activează din nou notificările pe acest dispozitiv.')
      }
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <section className="team-panel" aria-labelledby="push-heading">
    <h2 id="push-heading">Notificări de activitate</h2>
    <p>Primești alerte când colegii se conectează sau lucrează cu rapoartele. Activează-le pe fiecare dispozitiv.</p>
    {!supported && <p>Pe iPhone, adaugă PLUP pe ecranul principal din Safari și deschide aplicația de acolo. Pe desktop sau Android, folosește un browser cu notificări push.</p>}
    {supported && <div className="team-actions">
      <Button type="button" variant={active ? 'outline' : 'default'} disabled={!registration || busy}
        onClick={() => void change(active ? 'disable' : 'enable')}>
        <Bell aria-hidden="true" />{active ? 'Dezactivează pe acest dispozitiv' : 'Activează pe acest dispozitiv'}
      </Button>
      {active && <Button type="button" variant="outline" disabled={busy} onClick={() => void change('test')}>
        Trimite o notificare de test
      </Button>}
    </div>}
    <p className="team-status" role="status">{status}</p>
  </section>
}
