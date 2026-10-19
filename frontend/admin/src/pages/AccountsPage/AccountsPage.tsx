import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Eye, EyeOff, KeyRound, Search, UserPlus, UserCog } from 'lucide-react'
import { createAccount, getAccounts, updateAccount } from '../../api/operations'
import type { AccountAdmin } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './AccountsPage.css'

const roleOptions = [
  'emergency_coordinator',
  'clinician',
  'provider_responder',
  'patient',
  'emergency_contact',
]

const words = (value: string) => value.replaceAll('_', ' ')
const initials = (name: string) => name.slice(0, 2).toUpperCase() || 'U'

function RoleChips({ value, onChange }: { value: string; onChange: (role: string) => void }) {
  return (
    <div className="ui-field">
      <span>Role</span>
      <div className="role-chips" role="group" aria-label="Role">
        {roleOptions.map((role) => (
          <button key={role} type="button" className={`ui-chip${value === role ? ' is-on' : ''}`} onClick={() => onChange(role)} aria-pressed={value === role}>{words(role)}</button>
        ))}
      </div>
    </div>
  )
}

function PasswordField({ label, value, onChange, placeholder, required }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; required?: boolean }) {
  const [shown, setShown] = useState(false)
  return (
    <label className="ui-field">
      {label}
      <span className="ui-input-wrap">
        <input type={shown ? 'text' : 'password'} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} required={required} autoComplete="new-password" />
        <button type="button" onClick={() => setShown((v) => !v)} aria-label={shown ? 'Hide password' : 'Show password'} aria-pressed={shown}>{shown ? <EyeOff size={16} /> : <Eye size={16} />}</button>
      </span>
    </label>
  )
}

export function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountAdmin[]>([])
  const [selectedAccount, setSelectedAccount] = useState<AccountAdmin | null>(null)
  const [panel, setPanel] = useState<'edit' | 'create'>('edit')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [createDraft, setCreateDraft] = useState({
    username: '',
    email: '',
    password: '',
    role: 'clinician',
    phone_number: '',
    is_active: true,
    patient: '',
  })
  const [editDraft, setEditDraft] = useState({
    email: '',
    password: '',
    role: 'clinician',
    phone_number: '',
    is_active: true,
    patient: '',
  })

  async function loadAccounts() {
    const next = await getAccounts(search)
    setAccounts(next)
    if (next.length > 0) {
      const selected = selectedAccount ? next.find((item) => item.id === selectedAccount.id) || next[0] : next[0]
      setSelectedAccount(selected)
      setEditDraft({
        email: selected.email || '',
        password: '',
        role: selected.role || 'clinician',
        phone_number: selected.phone_number || '',
        is_active: selected.is_active,
        patient: selected.patient || '',
      })
    } else {
      setSelectedAccount(null)
    }
  }

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      getAccounts('')
        .then((next) => {
          if (!active) return
          setAccounts(next)
          if (next.length > 0) {
            const selected = next[0]
            setSelectedAccount(selected)
            setEditDraft({
              email: selected.email || '',
              password: '',
              role: selected.role || 'clinician',
              phone_number: selected.phone_number || '',
              is_active: selected.is_active,
              patient: selected.patient || '',
            })
          } else {
            setSelectedAccount(null)
          }
        })
        .catch((reason: Error) => {
          if (active) setError(reason.message)
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, 0)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [])

  async function handleSearch(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await loadAccounts()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load accounts.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await createAccount({
        ...createDraft,
        patient: createDraft.role === 'patient' ? (createDraft.patient || null) : null,
      })
      setCreateDraft({ username: '', email: '', password: '', role: 'clinician', phone_number: '', is_active: true, patient: '' })
      await loadAccounts()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to create account.')
    } finally {
      setBusy(false)
    }
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault()
    if (!selectedAccount) return
    setBusy(true)
    setError('')
    try {
      await updateAccount(selectedAccount.id, {
        email: editDraft.email,
        password: editDraft.password || undefined,
        role: editDraft.role,
        phone_number: editDraft.phone_number,
        is_active: editDraft.is_active,
        patient: editDraft.role === 'patient' ? (editDraft.patient || null) : null,
      })
      await loadAccounts()
      setEditDraft((current) => ({ ...current, password: '' }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update account.')
    } finally {
      setBusy(false)
    }
  }

  function selectAccount(account: AccountAdmin) {
    setSelectedAccount(account)
    setPanel('edit')
    setEditDraft({
      email: account.email || '',
      password: '',
      role: account.role || 'clinician',
      phone_number: account.phone_number || '',
      is_active: account.is_active,
      patient: account.patient || '',
    })
  }

  const activePanel = panel === 'edit' && selectedAccount ? 'edit' : 'create'

  return (
    <div className="ui-page accounts-page">
      <header className="ui-head">
        <div>
          <h1>Account and role administration</h1>
          <p>Provision and maintain operational user access without relying on Django admin.</p>
        </div>
        <span className="ui-pill"><strong>{accounts.length}</strong> accounts</span>
      </header>

      {error && <div className="ui-error" role="alert">{error}</div>}

      <div className="accounts-grid">
        {/* ---------- Directory ---------- */}
        <section className="ui-panel">
          <div className="ui-panel__head"><h2><span className="ui-panel__icon"><KeyRound size={16} /></span> Current users</h2></div>
          <form className="account-search" onSubmit={handleSearch}>
            <div className="ui-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search username…" aria-label="Search accounts" /></div>
            <button type="submit" className="ui-btn ui-btn--soft ui-btn--sm">Search</button>
          </form>

          {loading ? (
            <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" /><div className="ui-skeleton" /><div className="ui-skeleton" /></div>
          ) : accounts.length === 0 ? (
            <EmptyState icon={KeyRound} title="No accounts found" detail="Try another search or create a new account." />
          ) : (
            <div className="account-list">
              {accounts.map((account, index) => (
                <button key={account.id} type="button" className={`account-row${selectedAccount?.id === account.id ? ' is-selected' : ''}`} style={{ animationDelay: `${Math.min(index, 10) * 30}ms` }} onClick={() => selectAccount(account)}>
                  <span className="ui-avatar">{initials(account.username)}</span>
                  <span className="account-row__main"><strong>{account.username}</strong><small>{account.email || 'No email set'}</small></span>
                  <span className="account-meta"><StatusBadge value={account.role || 'unknown'} /><StatusBadge value={account.is_active ? 'active' : 'inactive'} /></span>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* ---------- Edit / create ---------- */}
        <section className="ui-panel account-editor">
          <div className="account-tabs ui-segment" role="tablist" aria-label="Account actions">
            <button type="button" role="tab" aria-selected={activePanel === 'edit'} className={activePanel === 'edit' ? 'is-on' : undefined} onClick={() => setPanel('edit')} disabled={!selectedAccount}><UserCog size={15} /> Edit account</button>
            <button type="button" role="tab" aria-selected={activePanel === 'create'} className={activePanel === 'create' ? 'is-on' : undefined} onClick={() => setPanel('create')}><UserPlus size={15} /> New user</button>
          </div>

          {activePanel === 'edit' && selectedAccount ? (
            <form className="account-form" key={`edit-${selectedAccount.id}`} onSubmit={handleUpdate}>
              <div className="account-form__title">
                <span className="ui-avatar">{initials(selectedAccount.username)}</span>
                <div><h2>{selectedAccount.username}</h2><p className="ui-muted">Update access, contact details or reset the password.</p></div>
              </div>
              <label className="ui-field">Email<input type="email" value={editDraft.email} onChange={(event) => setEditDraft({ ...editDraft, email: event.target.value })} /></label>
              <PasswordField label="Reset password" value={editDraft.password} onChange={(password) => setEditDraft({ ...editDraft, password })} placeholder="Leave blank to keep existing password" />
              <RoleChips value={editDraft.role} onChange={(role) => setEditDraft({ ...editDraft, role })} />
              <label className="ui-field">Phone<input value={editDraft.phone_number} onChange={(event) => setEditDraft({ ...editDraft, phone_number: event.target.value })} /></label>
              {editDraft.role === 'patient' && <label className="ui-field">Patient ID<input value={editDraft.patient} onChange={(event) => setEditDraft({ ...editDraft, patient: event.target.value })} required /></label>}
              <label className="ui-switch"><input type="checkbox" role="switch" checked={editDraft.is_active} onChange={(event) => setEditDraft({ ...editDraft, is_active: event.target.checked })} /><span className="ui-switch__track" /><span>Active account</span></label>
              <button type="submit" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy}>Save changes</button>
            </form>
          ) : (
            <form className="account-form" key="create" onSubmit={handleCreate}>
              <div className="account-form__title">
                <span className="ui-avatar"><UserPlus size={18} /></span>
                <div><h2>Provision new user</h2><p className="ui-muted">Create an account and assign its role.</p></div>
              </div>
              <label className="ui-field">Username<input value={createDraft.username} onChange={(event) => setCreateDraft({ ...createDraft, username: event.target.value })} required /></label>
              <label className="ui-field">Email<input type="email" value={createDraft.email} onChange={(event) => setCreateDraft({ ...createDraft, email: event.target.value })} /></label>
              <PasswordField label="Password" value={createDraft.password} onChange={(password) => setCreateDraft({ ...createDraft, password })} required />
              <RoleChips value={createDraft.role} onChange={(role) => setCreateDraft({ ...createDraft, role })} />
              <label className="ui-field">Phone<input value={createDraft.phone_number} onChange={(event) => setCreateDraft({ ...createDraft, phone_number: event.target.value })} /></label>
              {createDraft.role === 'patient' && <label className="ui-field">Patient ID<input value={createDraft.patient} onChange={(event) => setCreateDraft({ ...createDraft, patient: event.target.value })} required /></label>}
              <label className="ui-switch"><input type="checkbox" role="switch" checked={createDraft.is_active} onChange={(event) => setCreateDraft({ ...createDraft, is_active: event.target.checked })} /><span className="ui-switch__track" /><span>Active account</span></label>
              <button type="submit" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy}><UserPlus size={16} /> Create account</button>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}