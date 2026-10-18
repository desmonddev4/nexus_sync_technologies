import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MeasurementReviewPage } from './MeasurementReviewPage'
import type { MeasurementQualityReview } from '../../types/api'

const { getMeasurementQualityQueue, reviewMeasurementQuality } = vi.hoisted(() => ({
  getMeasurementQualityQueue: vi.fn(),
  reviewMeasurementQuality: vi.fn(),
}))

vi.mock('../../api/operations', () => ({ getMeasurementQualityQueue, reviewMeasurementQuality }))

const reading: MeasurementQualityReview = {
  id: 'measurement-1',
  patient: 'patient-1',
  patient_name: 'Test Patient',
  device: null,
  event_id: 'event-1',
  measurement_type: 'heart_rate_bpm',
  value: '120',
  unit: 'bpm',
  source: 'simulator',
  quality: 'unreviewed',
  quality_reviewed_by: null,
  quality_reviewed_at: null,
  measured_at: new Date().toISOString(),
  received_at: new Date().toISOString(),
}

describe('MeasurementReviewPage', () => {
  beforeEach(() => {
    getMeasurementQualityQueue.mockReset().mockResolvedValue([reading])
    reviewMeasurementQuality.mockReset().mockResolvedValue({ ...reading, quality: 'acceptable' })
  })

  it('shows unreviewed measurements and removes the item after an audited review succeeds', async () => {
    render(<MeasurementReviewPage />)

    expect(await screen.findByText('Test Patient')).toBeInTheDocument()
    expect(screen.getByText(/may trigger a configured rule/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Accept heart_rate_bpm for Test Patient' }))

    await waitFor(() => expect(reviewMeasurementQuality).toHaveBeenCalledWith('measurement-1', 'acceptable'))
    await waitFor(() => expect(screen.getByText('Queue clear')).toBeInTheDocument())
  })
})
