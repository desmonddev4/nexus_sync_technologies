import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { KeyRound, Search, UserPlus } from 'lucide-react'
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

export function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountAdmin[]>([])
  const [selectedAccount, setSelectedAccount] = useState<AccountAdmin | null>(null)
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

  return (
    <div className="accounts-page">
      <header className="page-heading">
        <div>
          <p className="page-eyebrow">OPERATIONS / ACCESS</p>
          <h1>Account and role administration</h1>
          <p className="page-subtitle">Provision and maintain operational user access without relying on Django admin.</p>
        </div>
        <span className="accounts-count">{accounts.length} accounts</span>
      </header>

      {error && <div className="page-error" role="alert">{error}</div>}

      <form className="account-search" onSubmit={handleSearch}>
        <Search size={16} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search username…" aria-label="Search accounts" />
        <button type="submit">Search</button>
      </form>

      <div className="accounts-grid">
        <section className="detail-panel">
          <div className="detail-panel-heading"><div><p className="page-eyebrow">ACCOUNTS</p><h2>Current users</h2></div></div>
          {loading ? <div className="loading-row">Loading accounts…</div> : accounts.length === 0 ? <EmptyState icon={KeyRound} title="No accounts found" detail="Try another search or create a new account." /> : (
            <div className="account-list">{accounts.map((account) => <button key={account.id} type="button" className={`account-row${selectedAccount?.id === account.id ? ' is-selected' : ''}`} onClick={() => {
              setSelectedAccount(account)
              setEditDraft({
                email: account.email || '',
                password: '',
                role: account.role || 'clinician',
                phone_number: account.phone_number || '',
                is_active: account.is_active,
                patient: account.patient || '',
              })
            }}>
              <div><strong>{account.username}</strong><small>{account.email || 'No email set'}</small></div>
              <div className="account-meta"><StatusBadge value={account.role || 'unknown'} /><StatusBadge value={account.is_active ? 'active' : 'inactive'} /></div>
            </button>)}</div>
          )}
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading"><div><p className="page-eyebrow">CREATE ACCOUNT</p><h2>Provision new user</h2></div></div>
          <form className="account-form" onSubmit={handleCreate}>
            <label>Username<input value={createDraft.username} onChange={(event) => setCreateDraft({ ...createDraft, username: event.target.value })} required /></label>
            <label>Email<input type="email" value={createDraft.email} onChange={(event) => setCreateDraft({ ...createDraft, email: event.target.value })} /></label>
            <label>Password<input type="password" value={createDraft.password} onChange={(event) => setCreateDraft({ ...createDraft, password: event.target.value })} required /></label>
            <label>Role<select value={createDraft.role} onChange={(event) => setCreateDraft({ ...createDraft, role: event.target.value })}>{roleOptions.map((role) => <option key={role} value={role}>{role.replaceAll('_', ' ')}</option>)}</select></label>
            <label>Phone<input value={createDraft.phone_number} onChange={(event) => setCreateDraft({ ...createDraft, phone_number: event.target.value })} /></label>
            {createDraft.role === 'patient' && <label>Patient ID<input value={createDraft.patient} onChange={(event) => setCreateDraft({ ...createDraft, patient: event.target.value })} required /></label>}
            <label className="checkbox-row"><input type="checkbox" checked={createDraft.is_active} onChange={(event) => setCreateDraft({ ...createDraft, is_active: event.target.checked })} /> Active account</label>
            <button type="submit" disabled={busy}><UserPlus size={15} /> Create account</button>
          </form>
        </section>
      </div>

      {selectedAccount && (
        <section className="detail-panel">
          <div className="detail-panel-heading"><div><p className="page-eyebrow">EDIT ACCOUNT</p><h2>{selectedAccount.username}</h2></div></div>
          <form className="account-form" onSubmit={handleUpdate}>
            <label>Email<input type="email" value={editDraft.email} onChange={(event) => setEditDraft({ ...editDraft, email: event.target.value })} /></label>
            <label>Reset password<input type="password" value={editDraft.password} onChange={(event) => setEditDraft({ ...editDraft, password: event.target.value })} placeholder="Leave blank to keep existing password" /></label>
            <label>Role<select value={editDraft.role} onChange={(event) => setEditDraft({ ...editDraft, role: event.target.value })}>{roleOptions.map((role) => <option key={role} value={role}>{role.replaceAll('_', ' ')}</option>)}</select></label>
            <label>Phone<input value={editDraft.phone_number} onChange={(event) => setEditDraft({ ...editDraft, phone_number: event.target.value })} /></label>
            {editDraft.role === 'patient' && <label>Patient ID<input value={editDraft.patient} onChange={(event) => setEditDraft({ ...editDraft, patient: event.target.value })} required /></label>}
            <label className="checkbox-row"><input type="checkbox" checked={editDraft.is_active} onChange={(event) => setEditDraft({ ...editDraft, is_active: event.target.checked })} /> Active account</label>
            <button type="submit" disabled={busy}>Save changes</button>
          </form>
        </section>
      )}
    </div>
  )
}
