import { useCallback, useEffect, useState } from 'react'
import { Check, Clock3, RefreshCw, ShieldAlert, X } from 'lucide-react'
import { getMeasurementQualityQueue, reviewMeasurementQuality } from '../../api/operations'
import type { MeasurementQualityReview } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './MeasurementReviewPage.css'

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'P'

export function MeasurementReviewPage() {
  const [measurements, setMeasurements] = useState<MeasurementQualityReview[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setError('')
    try { setMeasurements(await getMeasurementQualityQueue()) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load the quality-review queue.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh() }, 0)
    return () => window.clearTimeout(timer)
  }, [refresh])

  async function decide(measurement: MeasurementQualityReview, quality: 'acceptable' | 'questionable') {
    setBusyId(measurement.id)
    setError('')
    try {
      await reviewMeasurementQuality(measurement.id, quality)
      setMeasurements((current) => current.filter((item) => item.id !== measurement.id))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to record the quality review.') }
    finally { setBusyId('') }
  }

  return (
    <div className="ui-page measurement-review-page">
      <header className="ui-head">
        <div>
          <h1>Measurement review</h1>
          <p>Clinician review is required before readings can be evaluated by monitoring rules.</p>
        </div>
        <button className="ui-btn ui-btn--ghost" type="button" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'mr-spin' : undefined} /> Refresh queue
        </button>
      </header>

      <div className="ui-notice" role="note">
        <ShieldAlert size={16} />
        <span>Accepting a reading may trigger a configured rule. Review sensor quality and context; this screen does not provide a diagnosis.</span>
      </div>

      {error && <div className="ui-error" role="alert">{error}</div>}

      <section className="ui-panel">
        <div className="ui-panel__head">
          <h2><span className="ui-panel__icon"><Clock3 size={16} /></span> Unreviewed readings</h2>
          <span className="ui-pill"><strong>{measurements.length}</strong> awaiting review</span>
        </div>

        {loading ? (
          <div className="mr-grid" aria-busy="true"><div className="ui-skeleton" style={{ height: 190 }} /><div className="ui-skeleton" style={{ height: 190 }} /><div className="ui-skeleton" style={{ height: 190 }} /></div>
        ) : measurements.length === 0 ? (
          <EmptyState icon={Check} title="Queue clear" detail="There are no unreviewed measurements in the current review batch." />
        ) : (
          <div className="mr-grid">
            {measurements.map((measurement, index) => (
              <article className={`mr-card${busyId === measurement.id ? ' is-busy' : ''}`} key={measurement.id} style={{ animationDelay: `${Math.min(index, 9) * 45}ms` }}>
                <header>
                  <span className="ui-avatar">{initials(measurement.patient_name)}</span>
                  <div><strong>{measurement.patient_name}</strong><small>{new Date(measurement.measured_at).toLocaleString()}</small></div>
                </header>

                <div className="mr-reading">
                  <span className="mr-reading__type">{measurement.measurement_type.replaceAll('_', ' ')}</span>
                  <strong>{measurement.value}<em>{measurement.unit}</em></strong>
                </div>

                <div className="mr-meta">
                  <span className="ui-tag">{measurement.source}</span>
                  <StatusBadge value={measurement.quality} />
                </div>

                <div className="measurement-review-actions">
                  <button type="button" className="ui-btn ui-btn--ok" aria-label={`Accept ${measurement.measurement_type} for ${measurement.patient_name}`} disabled={busyId === measurement.id} onClick={() => void decide(measurement, 'acceptable')}><Check size={15} /> Accept</button>
                  <button type="button" className="ui-btn ui-btn--danger" aria-label={`Mark ${measurement.measurement_type} questionable for ${measurement.patient_name}`} disabled={busyId === measurement.id} onClick={() => void decide(measurement, 'questionable')}><X size={15} /> Questionable</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}