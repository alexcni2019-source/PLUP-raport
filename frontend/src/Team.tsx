import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { RefreshCw, ShieldCheck, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Role = 'editor' | 'viewer'
type Member = { id: string; username: string; name: string; role: Role; modules: string[]; active: boolean; activated: boolean }
type AccessEvent = { id: number; created_at: string; actor: string; action: string }
type Listing = { members: Member[]; events: AccessEvent[] }
const groups = [
  { label: 'Producție · o zi și trei zile', modes: ['weekday', 'weekend'] },
  { label: 'Plan de producție', modes: ['plan'] },
  { label: 'Previz', modes: ['forecast'] },
]
const all = groups.flatMap(group => group.modes)
const actions: Record<string, string> = {
  'member-create': 'Cont creat', 'password-set': 'Parolă setată', permissions: 'Permisiuni schimbate',
  revoke: 'Acces revocat', login: 'Conectare', logout: 'Deconectare',
  invite: 'Invitație creată', reissue: 'Acces resetat', activate: 'Cont activat',
  'report-create': 'Raport creat', 'report-edit': 'Raport modificat', 'report-restore': 'Versiune restaurată',
}

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await window.PLUPFetch(path, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : {})
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || 'Operațiunea nu a reușit.')
  return result
}

function RoleField({ value, onChange }: { value: Role; onChange: (role: Role) => void }) {
  return <label>Rol<select aria-label="Rol" value={value} onChange={event => onChange(event.target.value as Role)}>
    <option value="viewer">Cititor · consultă și exportă</option>
    <option value="editor">Editor · creează și modifică</option>
  </select></label>
}

function Modules({ value, onChange }: { value: string[]; onChange: (modes: string[]) => void }) {
  return <fieldset className="team-modules"><legend>Module permise</legend>
    {groups.map(group => <label key={group.label}>
      <input type="checkbox" checked={group.modes.every(mode => value.includes(mode))}
        onChange={event => onChange(event.target.checked
          ? [...new Set([...value, ...group.modes])]
          : value.filter(mode => !group.modes.includes(mode)))} />
      <span>{group.label}</span>
    </label>)}
  </fieldset>
}

function PasswordField({ label, value, onChange }: {
  label: string; value: string; onChange: (password: string) => void
}) {
  return <label>{label}<input type="password" autoComplete="new-password" minLength={12} maxLength={128}
    required value={value} onChange={event => onChange(event.target.value)} />
    <small>Între 12 și 128 de caractere.</small>
  </label>
}

function MemberCard({ member, refresh }: { member: Member; refresh: () => Promise<void> }) {
  const [role, setRole] = useState(member.role)
  const [modules, setModules] = useState(member.modules)
  const [editing, setEditing] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const moduleKey = member.modules.join(',')
  useEffect(() => { setRole(member.role); setModules(moduleKey.split(',')) }, [member.role, moduleKey])

  async function update(action: 'permissions' | 'password' | 'revoke') {
    if (busy || (action === 'revoke' && !confirm('Retragi accesul pentru ' + member.username + '?'))) return
    setBusy(true)
    setStatus('Se actualizează…')
    try {
      const changes = action === 'password' ? { password } : action === 'permissions' ? { role, modules } : {}
      await request('/api/admin/members/update', { id: member.id, action, ...changes })
      setPassword('')
      setEditing(false)
      setStatus({
        permissions: 'Permisiuni actualizate.', password: 'Parola a fost setată. Sesiunile anterioare s-au închis.',
        revoke: 'Acces retras.',
      }[action])
      await refresh()
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <article className="team-member">
    <div className="team-member-heading">
      <div><h3>{member.name || member.username}</h3>{member.name && <p>{member.username}</p>}</div>
      <span className={'team-state' + (member.active ? '' : ' revoked')}>
        {!member.active ? 'Acces revocat' : member.activated ? 'Activ' : 'Parolă nesetată'}
      </span>
    </div>
    <fieldset className="team-fieldset" disabled={busy}>
      <div className="team-member-settings">
        <RoleField value={role} onChange={setRole} /><Modules value={modules} onChange={setModules} />
      </div>
      <div className="team-actions">
        <Button variant="outline" disabled={!modules.length} onClick={() => void update('permissions')}>Salvează permisiunile</Button>
        <Button variant="ghost" aria-expanded={editing} onClick={() => { setEditing(!editing); setPassword('') }}>
          {member.active && member.activated ? 'Schimbă parola' : 'Setează parola și activează'}
        </Button>
        {member.active && <Button variant="ghost" className="team-revoke" onClick={() => void update('revoke')}>Revocă accesul</Button>}
      </div>
    </fieldset>
    {editing && <form className="team-password-form" onSubmit={event => { event.preventDefault(); void update('password') }}>
      <fieldset className="team-fieldset" disabled={busy}>
        <PasswordField label="Parolă nouă" value={password} onChange={setPassword} />
        <p>{member.active ? 'Salvarea închide sesiunile active.' : 'Salvarea reactivează contul.'}</p>
        <Button type="submit">Salvează parola</Button>
      </fieldset>
    </form>}
    <p className="team-status" role="status">{status}</p>
  </article>
}

export default function Team() {
  const [data, setData] = useState<Listing>({ members: [], events: [] })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [modules, setModules] = useState(all)

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      setData(await request<Listing>('/api/admin/members'))
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void refresh() }, [])

  async function create(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setStatus('Se creează contul…')
    try {
      const result = await request<{ username: string }>('/api/admin/members/create', { username, name, password, role, modules })
      setUsername('')
      setName('')
      setPassword('')
      setStatus('Contul ' + result.username + ' este activ. Trimite-i colegului datele de conectare.')
      await refresh()
    } catch (error) {
      setStatus((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <div className="team-workspace">
    <section className="team-owner"><ShieldCheck aria-hidden="true" /><div>
      <strong>Tu administrezi accesul</strong><p>Creezi conturile, setezi parolele și alegi modulele permise.</p>
    </div></section>
    <section className="team-panel" aria-labelledby="team-create-title">
      <h2 id="team-create-title">Creează cont de coleg</h2>
      <form onSubmit={event => void create(event)}><fieldset className="team-fieldset" disabled={busy}>
        <div className="team-fields">
          <label>Utilizator<input value={username} onChange={event => setUsername(event.target.value)} minLength={3}
            maxLength={64} required autoComplete="off" autoCapitalize="none" spellCheck={false} placeholder="prenume.nume" /></label>
          <label>Nume, opțional<input value={name} onChange={event => setName(event.target.value)} maxLength={100} autoComplete="off" /></label>
          <PasswordField label="Parolă" value={password} onChange={setPassword} />
          <RoleField value={role} onChange={setRole} />
        </div>
        <Modules value={modules} onChange={setModules} />
        <Button type="submit" disabled={!modules.length}><UserPlus />{busy ? 'Se creează…' : 'Creează contul'}</Button>
      </fieldset></form>
      <p className="team-status" role="status">{status}</p>
      <p className="team-sign-in"><a href="/auth/member-login" target="_blank" rel="noopener">Pagina de conectare pentru colegi</a></p>
    </section>
    <section aria-labelledby="members-title">
      <div className="team-section-heading">
        <h2 id="members-title">Colegii tăi · {data.members.length}</h2>
        <Button variant="outline" disabled={loading} onClick={() => void refresh()}><RefreshCw />Reîncarcă</Button>
      </div>
      {loading && <p role="status">Se încarcă utilizatorii…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !data.members.length && <p>Nu ai creat încă niciun cont de coleg.</p>}
      {data.members.map(member => <MemberCard key={member.id} member={member} refresh={refresh} />)}
    </section>
    <section className="team-panel" aria-labelledby="events-title">
      <h2 id="events-title">Jurnal recent</h2>
      <ol className="team-journal">{data.events.map(event => {
        const actor = data.members.find(member => member.id === event.actor)
        return <li key={event.id}>
          <strong>{actions[event.action] || event.action}</strong>
          <span>{event.actor === 'owner' ? 'Proprietar' : actor?.name || actor?.username || 'Colegul'}</span>
          <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString('ro-RO', { timeZone: 'Europe/Bucharest' })}</time>
        </li>
      })}</ol>
    </section>
  </div>
}
