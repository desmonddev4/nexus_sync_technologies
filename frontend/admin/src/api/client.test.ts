import { describe, expect, it } from 'vitest'

import { normalizeApiBaseUrl } from './client'

describe('normalizeApiBaseUrl', () => {
  it('adds the API version to a bare backend origin', () => {
    expect(normalizeApiBaseUrl('https://nexus-sync-backend.onrender.com')).toBe(
      'https://nexus-sync-backend.onrender.com/api/v1',
    )
  })

  it('adds the API version to a backend origin with a trailing slash', () => {
    expect(normalizeApiBaseUrl('https://nexus-sync-backend.onrender.com/')).toBe(
      'https://nexus-sync-backend.onrender.com/api/v1',
    )
  })

  it('does not duplicate an API version already in the URL', () => {
    expect(normalizeApiBaseUrl('https://nexus-sync-backend.onrender.com/api/v1/')).toBe(
      'https://nexus-sync-backend.onrender.com/api/v1',
    )
  })

  it('preserves relative API paths used by local development', () => {
    expect(normalizeApiBaseUrl('/api/v1')).toBe('/api/v1')
  })
})
