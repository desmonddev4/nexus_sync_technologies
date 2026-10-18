import { useCallback, useEffect, useState } from 'react'
import { Check, RefreshCw, ShieldAlert, X } from 'lucide-react'
import { getMeasurementQualityQueue, reviewMeasurementQuality } from '../../api/operations'
import type { MeasurementQualityReview } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './MeasurementReviewPage.css'

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

  return <div className="measurement-review-page">
    <header className="page-heading"><div><p className="page-eyebrow">SAFETY / DATA QUALITY</p><h1>Measurement review</h1><p className="page-subtitle">Clinician review is required before readings can be evaluated by monitoring rules.</p></div><button className="measurement-review-refresh" type="button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={14} /> Refresh queue</button></header>
    <div className="measurement-review-notice"><ShieldAlert size={16} /><span>Accepting a reading may trigger a configured rule. Review sensor quality and context; this screen does not provide a diagnosis.</span></div>
    {error && <div className="page-error" role="alert">{error}</div>}
    <section className="detail-panel">
      <div className="detail-panel-heading"><div><p className="page-eyebrow">UNREVIEWED READINGS</p><h2>{measurements.length} awaiting review</h2></div></div>
      {loading ? <div className="loading-row">Loading measurement queue…</div> : measurements.length === 0 ? <EmptyState icon={Check} title="Queue clear" detail="There are no unreviewed measurements in the current review batch." /> : <div className="table-wrap"><table className="data-table measurement-review-table"><thead><tr><th>Patient</th><th>Measurement</th><th>Value</th><th>Source / quality</th><th>Measured</th><th>Decision</th></tr></thead><tbody>
        {measurements.map((measurement) => <tr key={measurement.id}><td>{measurement.patient_name}</td><td>{measurement.measurement_type.replaceAll('_', ' ')}</td><td>{measurement.value} {measurement.unit}</td><td>{measurement.source}<br /><StatusBadge value={measurement.quality} /></td><td>{new Date(measurement.measured_at).toLocaleString()}</td><td><div className="measurement-review-actions"><button type="button" aria-label={`Accept ${measurement.measurement_type} for ${measurement.patient_name}`} disabled={busyId === measurement.id} onClick={() => void decide(measurement, 'acceptable')}><Check size={14} /> Accept</button><button type="button" aria-label={`Mark ${measurement.measurement_type} questionable for ${measurement.patient_name}`} disabled={busyId === measurement.id} onClick={() => void decide(measurement, 'questionable')}><X size={14} /> Questionable</button></div></td></tr>)}
      </tbody></table></div>}
    </section>
  </div>
}
