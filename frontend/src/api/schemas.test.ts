import { describe, expect, it } from 'vitest'

import {
  gamesResponseSchema,
  metricValueSchema,
  seasonsResponseSchema,
  todayResponseSchema,
} from './schemas'
import { game, meta, valueMetric } from '@/test/fixtures'

describe('B11 response schemas', () => {
  it('parses seasons and ignores compatible additive fields', () => {
    const response = seasonsResponseSchema.parse({
      count: 1,
      next: null,
      previous: null,
      results: [{
        id: '11111111-1111-4111-8111-111111111111',
        year: 2099,
        label: 'Synthetic',
        starts_on: '2099-04-01',
        ends_on: '2099-10-31',
        status: 'ACTIVE',
        future_optional_field: true,
      }],
      meta,
      future_envelope_field: 'compatible',
    })
    expect(response.results[0].year).toBe(2099)
    expect(response.results[0]).not.toHaveProperty('future_optional_field')
  })

  it('parses Games and Today responses', () => {
    expect(gamesResponseSchema.parse({ count: 1, next: null, previous: null, results: [game], meta }).results).toHaveLength(1)
    const today = todayResponseSchema.parse({
      date: '2099-04-03',
      games: [game],
      recent_leaders: [],
      recent_leaders_availability: { state: 'NOT_APPLICABLE', reason: 'NO_GAMES' },
      scope: {
        season: 2099,
        subject: 'PLAYER',
        game_type: 'REGULAR',
        window: 'SEASON',
        requested_n: null,
        cutoff_date: '2099-04-03',
        cutoff_source: 'EXPLICIT',
      },
      coverage: [],
      meta,
    })
    expect(today.games[0].hr_count.value).toBe(0)
  })

  it('keeps numeric zero and decimal values as numbers', () => {
    expect(metricValueSchema.parse(valueMetric).value).toBe(0)
    expect(metricValueSchema.parse({ ...valueMetric, value: 0.5 }).value).toBe(0.5)
  })

  it('preserves semantic null and rejects malformed state/value combinations', () => {
    expect(metricValueSchema.parse({ ...valueMetric, state: 'UNKNOWN', value: null }).state).toBe('UNKNOWN')
    expect(() => metricValueSchema.parse({ ...valueMetric, state: 'UNKNOWN', value: 0 })).toThrow()
    expect(() => metricValueSchema.parse({ ...valueMetric, state: 'NEW_STATE', value: null })).toThrow()
    expect(() => gamesResponseSchema.parse({ count: 1, results: [game], meta })).toThrow()
    expect(() => gamesResponseSchema.parse({
      count: 1,
      next: null,
      previous: null,
      results: [{ ...game, official_date: '2099-99-99' }],
      meta,
    })).toThrow()
  })
})
