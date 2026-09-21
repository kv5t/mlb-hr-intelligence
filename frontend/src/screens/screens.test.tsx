import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { game, meta, player, team, UUIDS, valueMetric } from '@/test/fixtures'
import { renderApp } from '@/test/renderApp'

const seasonPage = {
  count: 1,
  next: null,
  previous: null,
  results: [{ id: UUIDS.season, year: 2099, label: 'Synthetic fixture season', starts_on: '2099-04-01', ends_on: '2099-04-30', status: 'COMPLETE' }],
  meta,
}
const unknownMetric = { ...valueMetric, state: 'UNKNOWN', value: null, numerator: null, reason: 'COVERAGE_UNKNOWN' }
const incompleteMetric = { ...valueMetric, state: 'INCOMPLETE', value: null, numerator: null, reason: 'SOURCE_TRUNCATED' }
const secondGame = { ...game, id: '77777777-7777-4777-8777-777777777777', scheduled_game_number: 2, status: 'SCHEDULED', finality: 'NOT_FINAL', home_score: null, away_score: null, hr_count: unknownMetric }
const thirdGame = { ...game, id: '88888888-8888-4888-8888-888888888888', official_date: '2099-04-04', hr_count: incompleteMetric }
const scope = { season: 2099, subject: 'PLAYER', game_type: 'REGULAR', window: 'SEASON', requested_n: null, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT' }
const today = {
  date: '2099-04-03', games: [game, secondGame, thirdGame],
  recent_leaders: [{
    player,
    metrics: {
      'player.hr': { ...valueMetric, value: 2, numerator: 2 },
      'player.hr_game_pct': { ...valueMetric, value: 50, unit: 'PERCENT', numerator: 1, denominator: 2 },
    },
    scope: { ...scope, subject_id: UUIDS.player, team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE', actual_game_count: 2, known_eligible_game_count: 2 },
    coverage: [],
  }],
  recent_leaders_availability: { state: 'UNKNOWN', reason: 'COVERAGE_UNKNOWN' },
  scope, coverage: [], meta,
}
const eventId = '99999999-9999-4999-8999-999999999999'
const detail = {
  game: { ...game, hr_count: { ...valueMetric, value: 1, numerator: 1 } },
  participants: [{ player, team: team(), participation_state: 'APPEARED', roles: ['BATTER'], pa_count: { ...valueMetric, value: 0, unit: 'PA', numerator: 0 } }],
  home_runs: [{ id: eventId, game_id: UUIDS.game, plate_appearance_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', official_date: '2099-04-03', batter: player, pitcher: null, batting_team: team(), inning: 4, half_inning: 'BOTTOM', game_pa_ordinal: 12, provenance: { source_label: 'Synthetic fixture assertions only', retrieved_at: meta.data_as_of } }],
  coverage: [{ domain: 'SCHEDULE', state: 'COMPLETE', reason_codes: [] }, { domain: 'HR_EVENTS', state: 'PARTIAL', reason_codes: ['SOURCE_TRUNCATED'] }],
  meta,
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

function installApi(options: { todayResponses?: Response[] } = {}) {
  const todayResponses = [...(options.todayResponses ?? [json(today)])]
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith('/api/v1/seasons/')) return json(seasonPage)
    if (url.startsWith('/api/v1/teams/')) return json({ ...seasonPage, results: [team()] })
    if (url.startsWith(`/api/v1/games/${UUIDS.game}/`)) return json(detail)
    if (url.startsWith('/api/v1/games/')) return json({ ...seasonPage, count: 3, next: '/api/v1/games/?page=2', results: [game, secondGame, thirdGame] })
    if (url.startsWith('/api/v1/today/')) return todayResponses.shift() ?? json(today)
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('Today vertical slice', () => {
  it('keeps known games visible and distinguishes zero, unknown, incomplete, and leader availability', async () => {
    installApi()
    renderApp('/today?season=2099&date=2099-04-03&window=SEASON')
    expect(await screen.findByRole('heading', { name: 'Games' })).toBeInTheDocument()
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Partial data').length).toBeGreaterThan(0)
    expect(screen.getByText(/ranking completeness is unknown/i)).toBeInTheDocument()
    expect(screen.getByText('Observed rank 1')).toBeInTheDocument()
  })

  it('retries a 503 without losing the explicit URL scope', async () => {
    const unavailable = json({ error: { code: 'REVISION_UNAVAILABLE', message: 'No current revision.', details: {} }, meta: { dataset_revision: null, data_as_of: null } }, 503)
    installApi({ todayResponses: [unavailable, json(today)] })
    renderApp('/today?season=2099&date=2099-04-03&window=30G')
    expect(await screen.findByRole('heading', { name: 'Service temporarily unavailable' })).toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toHaveValue('2099-04-03')
    expect(screen.getByLabelText('Leader window')).toHaveValue('30G')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Games' })).toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toHaveValue('2099-04-03')
  })

  it('canonicalizes missing Today scope from season data and local date', async () => {
    const fetchMock = installApi()
    renderApp('/today')
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith('/api/v1/today/?date='))).toBe(true))
    expect(screen.getByLabelText('Season')).toHaveValue('2099')
  })
})

describe('Games vertical slice', () => {
  it('sends URL filters, preserves doubleheader rows, and shows nonfinal games', async () => {
    const fetchMock = installApi()
    renderApp(`/games?season=2099&date_from=2099-04-03&date_to=2099-04-03&team=${UUIDS.teamA}&status=COMPLETED&ordering=-official_date&page=1`)
    expect(await screen.findByRole('heading', { name: 'Games' })).toBeInTheDocument()
    const request = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => url.startsWith('/api/v1/games/'))
    expect(request).toContain('date_from=2099-04-03')
    expect(request).toContain('ordering=-official_date')
    expect(await screen.findAllByRole('link', { name: 'Open' })).toHaveLength(3)
    expect(screen.getAllByText('SCHEDULED').length).toBeGreaterThan(0)
  })

  it('rejects route-specific parameters before making a games request', () => {
    const fetchMock = installApi()
    renderApp('/games?window=7G')
    expect(screen.getByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith('/api/v1/games/'))).toBe(false)
  })

  it('paginates through server state without losing scope', async () => {
    const fetchMock = installApi()
    renderApp('/games?season=2099&page=1')
    fireEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/v1/games/?page=2&season=2099'))).toBe(true))
  })
})

describe('Game detail vertical slice', () => {
  it('renders authoritative total, coverage, zero-PA participant, and unknown pitcher', async () => {
    installApi()
    renderApp(`/games/${UUIDS.game}`)
    expect(await screen.findByRole('heading', { name: /SYN at SYN/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Evidence coverage' })).toBeInTheDocument()
    expect(within(screen.getByRole('table', { name: 'Positively evidenced game participants' })).getByText('0')).toBeInTheDocument()
    expect(screen.getByText('Pitcher:').parentElement).toHaveTextContent('Unknown')
    expect(screen.getByText(/Some game evidence is not complete/)).toBeInTheDocument()
  })

  it('focuses a valid HR fragment and handles missing focus safely', async () => {
    installApi()
    const { unmount } = renderApp(`/games/${UUIDS.game}#hr-${eventId}`)
    expect(await screen.findByText('Requested event')).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toHaveAttribute('id', `hr-${eventId}`))
    unmount()
    renderApp(`/games/${UUIDS.game}#hr-${UUIDS.teamB}`)
    expect(await screen.findByText(/Requested home-run event is not available/)).toBeInTheDocument()
  })

  it('uses safe return context', async () => {
    installApi()
    renderApp({ pathname: `/games/${UUIDS.game}`, state: { from: '/games?season=2099&page=2' } })
    expect(await screen.findByRole('link', { name: '← Back' })).toHaveAttribute('href', '/games?season=2099&page=2')
  })
})
