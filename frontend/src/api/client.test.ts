import { describe, expect, it } from 'vitest'

import { apiUrl } from './client'

describe('apiUrl', () => {
  it('serializes query values without inventing a trailing question mark', () => {
    expect(apiUrl('/api/health')).toMatch(/\/api\/health$/)
    expect(apiUrl('/api/datasets/example/preview', { limit: 20 })).toContain('limit=20')
  })
})
