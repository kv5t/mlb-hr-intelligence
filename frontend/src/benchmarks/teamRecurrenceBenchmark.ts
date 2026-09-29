import type { MatrixCell, TeamRecurrenceResponse } from '@/api'

const uuid = (value: number) => `00000000-0000-4000-8000-${value.toString(16).padStart(12, '0')}`
const metric = (value: number, unit = 'HR') => ({
  state: 'VALUE' as const,
  value,
  unit,
  numerator: value,
  denominator: null,
  reason: null,
})

const states = [
  'HR_COUNT', 'KNOWN_ZERO', 'DNP', 'ZERO_PA_APPEARANCE',
  'NOT_WITH_TEAM', 'UNKNOWN', 'INCOMPLETE',
] as const

function cell(row: number, column: number): MatrixCell {
  const state = states[(row * 3 + column) % states.length]
  if (state === 'HR_COUNT') {
    const count = (row + column) % 11 === 0 ? 2 : 1
    return {
      state,
      hr_count: count,
      home_run_event_ids: Array.from({ length: count }, (_, index) => uuid(400_000 + row * 1_000 + column * 3 + index)),
      reason: null,
    }
  }
  if (state === 'KNOWN_ZERO') return { state, hr_count: 0, home_run_event_ids: [], reason: null }
  return { state, hr_count: null, home_run_event_ids: [], reason: state === 'UNKNOWN' ? 'SOURCE_UNAVAILABLE' : null }
}

/** Deterministic synthetic matrix used by B19 tests and production-build measurements. */
export function createTeamRecurrenceBenchmark(rows = 60, columns = 162): TeamRecurrenceResponse {
  const team = {
    id: uuid(1), mlb_id: null, display_name: 'Benchmark Club', abbreviation: 'BEN',
    league: null, division: null,
  }
  const opponents = Array.from({ length: 5 }, (_, index) => ({
    id: uuid(10 + index), mlb_id: null, display_name: `Opponent ${index + 1}`,
    abbreviation: `O${index + 1}`, league: null, division: null,
  }))
  const start = Date.UTC(2099, 3, 1)
  const matrixColumns = Array.from({ length: columns }, (_, index) => ({
    game_id: uuid(1_000 + index),
    official_date: new Date(start + index * 86_400_000).toISOString().slice(0, 10),
    scheduled_game_number: index % 23 === 1 ? 2 : 1,
    opponent: opponents[index % opponents.length],
    home_away: (index % 2 ? 'AWAY' : 'HOME') as 'HOME' | 'AWAY',
    game_status: 'COMPLETED' as const,
    coverage: [{ domain: 'HR_EVENTS' as const, state: 'COMPLETE' as const, reason_codes: [] }],
  }))
  const matrixRows = Array.from({ length: rows }, (_, row) => {
    const cells = matrixColumns.map((_, column) => cell(row, column))
    const windowHr = cells.reduce((total, item) => total + (item.state === 'HR_COUNT' ? item.hr_count : 0), 0)
    return {
      player: {
        id: uuid(10_000 + row), mlb_id: null, display_name: `Benchmark Player ${String(row + 1).padStart(2, '0')}`,
        given_name: 'Benchmark', family_name: `Player ${row + 1}`, bats: 'R' as const,
        throws: 'R' as const, primary_position: 'OF', represented_team: null,
      },
      player_season_hr: metric(windowHr + (row % 8)),
      window_hr: metric(windowHr),
      cells,
    }
  })
  const metrics = Object.fromEntries([
    'hr', 'pa', 'hr_per_pa', 'pa_per_hr', 'hr_per_game', 'hr_games',
    'hr_game_pct', 'multi_hr_games', 'avg_hr_gap_games', 'median_hr_gap_games',
    'current_hr_drought_games', 'max_hr_drought_games',
    'current_hr_streak_games', 'max_hr_streak_games',
  ].map((name) => [`team.${name}`, metric(name === 'hr' ? 321 : 4)])) as TeamRecurrenceResponse['metrics']
  return {
    team,
    scope: {
      season: 2099, subject: 'TEAM', subject_id: team.id, game_type: 'REGULAR',
      window: 'SEASON', requested_n: null, cutoff_date: '2099-09-09', cutoff_source: 'EXPLICIT',
      team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE',
      actual_game_count: columns, known_eligible_game_count: columns,
    },
    metrics,
    columns: matrixColumns,
    rows: matrixRows,
    coverage: [
      { domain: 'SCHEDULE', state: 'COMPLETE', reason_codes: [] },
      { domain: 'PARTICIPATION', state: 'COMPLETE', reason_codes: [] },
      { domain: 'PLATE_APPEARANCES', state: 'COMPLETE', reason_codes: [] },
      { domain: 'HR_EVENTS', state: 'COMPLETE', reason_codes: [] },
    ],
    meta: { dataset_revision: 'benchmark-1', data_as_of: '2099-09-10T00:00:00Z' },
  }
}

declare global {
  interface Window {
    __matrixPayloadAvailableAt?: number
    __matrixPayloadBytes?: number
    __matrixHeapBaseline?: number
    __matrixLongestTask?: number
    __matrixInteractionStart?: number
    __matrixInteractionLongestTask?: number
  }
}

/** Installs deterministic same-origin responses only in an explicit benchmark build. */
export function installTeamRecurrenceBenchmarkFetch() {
  const measuredPerformance = performance as Performance & { memory?: { usedJSHeapSize: number } }
  window.__matrixHeapBaseline = measuredPerformance.memory?.usedJSHeapSize
  window.__matrixLongestTask = 0
  window.__matrixInteractionLongestTask = 0
  const beginInteractionSample = () => {
    window.__matrixInteractionStart = performance.now()
    window.__matrixInteractionLongestTask = 0
    document.querySelector<HTMLElement>('[data-matrix-ready]')?.setAttribute('data-interaction-longest-task-ms', '0')
  }
  window.addEventListener('keydown', beginInteractionSample, true)
  window.addEventListener('scroll', beginInteractionSample, true)
  if ('PerformanceObserver' in window) {
    try {
      new PerformanceObserver((entries) => {
        for (const entry of entries.getEntries()) {
          window.__matrixLongestTask = Math.max(window.__matrixLongestTask ?? 0, entry.duration)
          if (window.__matrixInteractionStart !== undefined && entry.startTime >= window.__matrixInteractionStart) {
            window.__matrixInteractionLongestTask = Math.max(window.__matrixInteractionLongestTask ?? 0, entry.duration)
            document.querySelector<HTMLElement>('[data-matrix-ready]')?.setAttribute(
              'data-interaction-longest-task-ms', String(window.__matrixInteractionLongestTask),
            )
          }
        }
      }).observe({ type: 'longtask', buffered: true })
    } catch { /* Long Tasks are not exposed by every browser. */ }
  }
  const payload = createTeamRecurrenceBenchmark()
  window.__matrixPayloadBytes = new TextEncoder().encode(JSON.stringify(payload)).byteLength
  const season = {
    count: 1, next: null, previous: null,
    results: [{
      id: uuid(90), year: 2099, label: 'Benchmark 2099',
      starts_on: '2099-04-01', ends_on: '2099-10-31', status: 'COMPLETE',
    }],
    meta: payload.meta,
  }
  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    const url = String(input)
    if (url.startsWith('/api/v1/seasons/')) {
      return new Response(JSON.stringify(season), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (/^\/api\/v1\/teams\/[^/]+\/recurrence\//.test(url)) {
      window.__matrixPayloadAvailableAt = performance.now()
      return new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    return originalFetch(input, init)
  }
}
