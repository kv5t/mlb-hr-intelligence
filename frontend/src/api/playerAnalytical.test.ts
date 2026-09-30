import { describe, it, expect } from 'vitest'
import { playerDetailResponseSchema, playerRecurrenceResponseSchema, playerHomeRunsResponseSchema } from './schemas'
import { normalizePlayerDetailParams, normalizePlayerRecurrenceParams, normalizePlayerHomeRunsParams } from './params'
import { queryKeys } from './queryKeys'
import { parseUrlState, updateUrlState } from '@/routing/urlState'
import { playerScopeSearch } from '@/screens/playerAnalyticalState'
import { playerDetail, playerRecurrence, playerHomeRuns, playerMetricIds } from '@/test/playerAnalyticalFixtures'
import { team, UUIDS, valueMetric } from '@/test/fixtures'

describe('B20 Player API boundary', () => {
  it('requires every displayed Player KPI and accepts additional compatible metrics', () => {
    expect(playerDetailResponseSchema.parse(playerDetail).player.represented_team).toBeNull()
    expect(playerDetailResponseSchema.parse({ ...playerDetail, player: { ...playerDetail.player, represented_team: team() }, metrics: { ...playerDetail.metrics, 'player.future': valueMetric } }).metrics['player.future']).toBeDefined()
    for (const id of playerMetricIds) {
      const metrics = { ...playerDetail.metrics }; delete metrics[`player.${id}`]
      expect(playerDetailResponseSchema.safeParse({ ...playerDetail, metrics }).success).toBe(false)
    }
  })
  it('rejects missing identity, meta, wrong subject and malformed KPI', () => {
    for (const field of ['player', 'scope', 'meta']) expect(playerDetailResponseSchema.safeParse({ ...playerDetail, [field]: undefined }).success).toBe(false)
    expect(playerDetailResponseSchema.safeParse({ ...playerDetail, scope: { ...playerDetail.scope, subject: 'TEAM' } }).success).toBe(false)
    expect(playerDetailResponseSchema.safeParse({ ...playerDetail, metrics: { ...playerDetail.metrics, 'player.hr': { ...valueMetric, value: '0' } } }).success).toBe(false)
  })
  it('validates observations, historical teams and server gap MetricValues', () => {
    const result = playerRecurrenceResponseSchema.parse(playerRecurrence)
    expect(result.observations[1].represented_teams[0].display_name).toBe('Historical B')
    expect(result.gaps.map((gap) => gap.non_hr_games.value)).toEqual([0, 2])
    expect(playerRecurrenceResponseSchema.safeParse({ ...playerRecurrence, observations: [{ ...playerRecurrence.observations[0], game_id: 'bad' }] }).success).toBe(false)
    expect(playerRecurrenceResponseSchema.safeParse({ ...playerRecurrence, gaps: [{ ...playerRecurrence.gaps[0], to_game_id: 'bad' }] }).success).toBe(false)
    expect(playerRecurrenceResponseSchema.safeParse({ ...playerRecurrence, observations: [{ ...playerRecurrence.observations[0], represented_teams: null }] }).success).toBe(false)
  })
  it('keeps listed count independent of authoritative total and reuses safe event schema', () => {
    const result = playerHomeRunsResponseSchema.parse(playerHomeRuns)
    expect(result.count).toBe(3); expect(result.total_hr.state).toBe('INCOMPLETE'); expect(result.total_hr.value).toBeNull()
    expect(result.results[0].pitcher).toBeNull()
    expect(playerHomeRunsResponseSchema.safeParse({ ...playerHomeRuns, results: [{ ...playerHomeRuns.results[0], game_id: 'bad' }] }).success).toBe(false)
  })
  it('normalizes only supported params and scopes keys by every analytical input', () => {
    const scope = { season: 2099, window: '30G' as const, team: UUIDS.teamA, home_away: 'AWAY' as const, cutoff: '2099-04-03' }
    for (const normalize of [normalizePlayerDetailParams, normalizePlayerRecurrenceParams]) expect(normalize({ ...scope, hr_page: 2, search: 'x', dataset_revision: '8' })).toEqual(scope)
    expect(normalizePlayerHomeRunsParams({ ...scope, ordering: '-official_date', page: 2, hr_page: 4 })).toEqual({ ...scope, ordering: '-official_date', page: 2 })
    expect(queryKeys.playerDetail(UUIDS.player, scope)).not.toEqual(queryKeys.playerDetail(UUIDS.player, { ...scope, window: '7G' }))
    expect(queryKeys.playerRecurrence(UUIDS.player, scope)).not.toEqual(queryKeys.playerDetail(UUIDS.player, scope))
    expect(queryKeys.playerHomeRuns(UUIDS.player, { ...scope, page: 1 })).not.toEqual(queryKeys.playerHomeRuns(UUIDS.player, { ...scope, page: 2 }))
  })
  it('validates route-specific scope and strips HR UI state from cross-page links', () => {
    const source = new URLSearchParams(`season=2099&window=30G&team=${UUIDS.teamA}&home_away=AWAY&cutoff=2099-04-03&hr_page=2&hr_ordering=-official_date`)
    const parsed = parseUrlState(source, 'playerHomeRuns'); expect(parsed.issues).toEqual([])
    const shared = playerScopeSearch(parsed.state)
    expect(shared).not.toContain('hr_'); expect(parseUrlState(new URLSearchParams(shared), 'playerRecurrence').issues).toEqual([])
    for (const route of ['playerDetail', 'playerRecurrence', 'playerHomeRuns'] as const) {
      for (const bad of ['season=0000', 'season=2099&season=2098', 'cutoff=bad', 'team=bad', 'search=x', 'dataset_revision=7']) expect(parseUrlState(new URLSearchParams(bad), route).issues.length).toBeGreaterThan(0)
    }
    const next = updateUrlState(source, { hr_page: '3' }); expect(parseUrlState(source, 'playerHomeRuns').state.hr_page).toBe('2'); expect(parseUrlState(next, 'playerHomeRuns').state.hr_page).toBe('3')
  })
})
