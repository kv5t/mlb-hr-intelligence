import { describe, expect, it } from 'vitest'

import { normalizeGamesParams, normalizePlayerLeaderboardParams } from './params'
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

  it('normalizes every leaderboard scope field without unsupported filters', () => {
    const normalized = normalizePlayerLeaderboardParams({
      season: 2099, window: '30G', team: UUIDS.teamA, home_away: 'HOME',
      cutoff: '2099-04-03', search: 'Fixture', position: '1B', bats: 'R',
      ordering: '-hr', page: 2, page_size: 25, league: 'AL', dataset_revision: '7',
    })
    expect(normalized).not.toHaveProperty('league')
    expect(normalized).not.toHaveProperty('dataset_revision')
    expect(queryKeys.playerLeaderboard(normalized)).toEqual(queryKeys.playerLeaderboard({ ...normalized }))
    expect(queryKeys.playerLeaderboard({ season: 2099, page: 1 })).not.toEqual(queryKeys.playerLeaderboard({ season: 2099, page: 2 }))
  })
})
