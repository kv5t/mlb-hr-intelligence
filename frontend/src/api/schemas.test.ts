import { describe, expect, it } from 'vitest'

import {
  gamesResponseSchema,
  metricValueSchema,
  playerLeaderboardResponseSchema,
  seasonsResponseSchema,
  todayResponseSchema,
  teamDetailSchema,
  teamHomeRunsResponseSchema,
  teamRecurrenceResponseSchema,
  matrixCellSchema,
} from './schemas'
import { game, meta, player, valueMetric } from '@/test/fixtures'
import { createTeamRecurrenceBenchmark } from '@/benchmarks/teamRecurrenceBenchmark'

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

  it('parses B14 leaderboard rows and rejects malformed scope enums', () => {
    const requiredMetrics = {
      'player.hr': valueMetric,
      'player.pa': valueMetric,
      'player.hr_per_pa': valueMetric,
      'player.pa_per_hr': valueMetric,
      'player.hr_per_game': valueMetric,
      'player.hr_game_pct': valueMetric,
      'player.median_hr_gap_games': valueMetric,
      'player.current_hr_drought_games': valueMetric,
    }
    const row = {
      player,
      metrics: { ...requiredMetrics, 'player.future_metric': valueMetric },
      scope: {
        season: 2099, subject: 'PLAYER', subject_id: player.id, game_type: 'REGULAR',
        window: '30G', requested_n: 30, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT',
        team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE',
        actual_game_count: 17, known_eligible_game_count: 17,
      },
      coverage: [],
    }
    const parsed = playerLeaderboardResponseSchema.parse({ count: 1, next: null, previous: null, results: [{ ...row, compatible_future_field: true }], meta })
    expect(parsed.results[0].scope.actual_game_count).toBe(17)
    expect(parsed.results[0].metrics['player.future_metric'].value).toBe(0)
    expect(parsed.results[0]).not.toHaveProperty('compatible_future_field')
    const missingRequiredMetric = Object.fromEntries(
      Object.entries(row.metrics).filter(([key]) => key !== 'player.pa'),
    )
    expect(() => playerLeaderboardResponseSchema.parse({ count: 1, next: null, previous: null, results: [{ ...row, metrics: missingRequiredMetric }], meta })).toThrow()
    expect(() => playerLeaderboardResponseSchema.parse({ count: 1, next: null, previous: null, results: [{ ...row, scope: { ...row.scope, selection_state: 'NEW' } }], meta })).toThrow()
  })

  it('validates team detail KPI completeness and team HR-log envelopes', () => {
    const teamMetrics = Object.fromEntries([
      'hr', 'pa', 'hr_per_pa', 'pa_per_hr', 'hr_per_game', 'hr_games',
      'hr_game_pct', 'multi_hr_games', 'avg_hr_gap_games', 'median_hr_gap_games',
      'current_hr_drought_games', 'max_hr_drought_games',
      'current_hr_streak_games', 'max_hr_streak_games',
    ].map((name) => [`team.${name}`, valueMetric]))
    const scope = {
      season: 2099, subject: 'TEAM', subject_id: game.home_team.id, game_type: 'REGULAR',
      window: '7G', requested_n: 7, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT',
      team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE',
      actual_game_count: 1, known_eligible_game_count: 1,
    }
    const detail = { team: game.home_team, metrics: { ...teamMetrics, 'team.future_metric': valueMetric }, scope, coverage: [], meta }
    expect(teamDetailSchema.parse(detail).metrics['team.future_metric'].value).toBe(0)
    expect(() => teamDetailSchema.parse({ ...detail, metrics: { ...teamMetrics, 'team.hr': undefined } })).toThrow()
    expect(teamHomeRunsResponseSchema.parse({ count: 0, next: null, previous: null, results: [], team: game.home_team, total_hr: valueMetric, scope, coverage: [], meta }).total_hr.value).toBe(0)
    expect(() => teamDetailSchema.parse({ ...detail, scope: { ...scope, subject: 'PLAYER' } })).toThrow()
  })

  it('validates the aligned Team recurrence response while allowing additive fields', () => {
    const response = createTeamRecurrenceBenchmark(2, 3)
    const parsed = teamRecurrenceResponseSchema.parse({ ...response, future_field: true })
    expect(parsed.rows).toHaveLength(2)
    expect(parsed.columns).toHaveLength(3)
    expect(() => teamRecurrenceResponseSchema.parse({
      ...response,
      rows: [{ ...response.rows[0], cells: response.rows[0].cells.slice(1) }],
    })).toThrow()
    expect(() => teamRecurrenceResponseSchema.parse({
      ...response,
      columns: [response.columns[0], response.columns[0]],
      rows: response.rows.map((row) => ({ ...row, cells: row.cells.slice(0, 2) })),
    })).toThrow()
    expect(() => teamRecurrenceResponseSchema.parse({
      ...response,
      columns: [{ ...response.columns[0], game_id: 'bad' }],
      rows: response.rows.map((row) => ({ ...row, cells: row.cells.slice(0, 1) })),
    })).toThrow()
  })

  it('enforces every discriminated MatrixCell invariant', () => {
    const eventId = '77777777-7777-4777-8777-777777777777'
    expect(matrixCellSchema.parse({ state: 'HR_COUNT', hr_count: 1, home_run_event_ids: [eventId], reason: null }).hr_count).toBe(1)
    expect(() => matrixCellSchema.parse({ state: 'HR_COUNT', hr_count: 0, home_run_event_ids: [], reason: null })).toThrow()
    expect(() => matrixCellSchema.parse({ state: 'HR_COUNT', hr_count: 2, home_run_event_ids: [eventId], reason: null })).toThrow()
    expect(matrixCellSchema.parse({ state: 'KNOWN_ZERO', hr_count: 0, home_run_event_ids: [], reason: null }).hr_count).toBe(0)
    expect(() => matrixCellSchema.parse({ state: 'KNOWN_ZERO', hr_count: null, home_run_event_ids: [], reason: null })).toThrow()
    for (const state of ['DNP', 'ZERO_PA_APPEARANCE', 'NOT_WITH_TEAM', 'UNKNOWN', 'INCOMPLETE'] as const) {
      expect(matrixCellSchema.parse({ state, hr_count: null, home_run_event_ids: [], reason: null }).state).toBe(state)
      expect(() => matrixCellSchema.parse({ state, hr_count: 0, home_run_event_ids: [], reason: null })).toThrow()
      expect(() => matrixCellSchema.parse({ state, hr_count: null, home_run_event_ids: [eventId], reason: null })).toThrow()
    }
  })
})
