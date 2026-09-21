import { describe, expect, it } from 'vitest'

import { normalizeGamesParams } from './params'
import { queryKeys } from './queryKeys'
import { shareDatasetRevision } from './revision'
import { UUIDS, meta } from '@/test/fixtures'

describe('query keys and parameters', () => {
  it('normalizes deterministic keys and includes every supported scope input', () => {
    const left = queryKeys.games({ team: UUIDS.teamA, season: 2099, page: 2 })
    const right = queryKeys.games({ page: 2, season: 2099, team: UUIDS.teamA })
    expect(left).toEqual(right)
    expect(queryKeys.games({ season: 2098 })).not.toEqual(queryKeys.games({ season: 2099 }))
    expect(queryKeys.games({ page: 1 })).not.toEqual(queryKeys.games({ page: 2 }))
  })

  it('never includes revision or unsupported fields', () => {
    const normalized = normalizeGamesParams({ season: 2099, dataset_revision: '9', cutoff: UUIDS.game })
    expect(normalized).toEqual({ season: 2099 })
    expect(JSON.stringify(queryKeys.games(normalized))).not.toContain('dataset_revision')
  })

  it('compares revisions without making them query inputs', () => {
    expect(shareDatasetRevision(meta, { ...meta })).toBe(true)
    expect(shareDatasetRevision(meta, { ...meta, dataset_revision: '8' })).toBe(false)
  })
})
