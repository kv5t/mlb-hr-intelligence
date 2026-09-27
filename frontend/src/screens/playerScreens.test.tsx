import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { meta, player, team, UUIDS, valueMetric } from '@/test/fixtures'
import { renderApp } from '@/test/renderApp'

const seasonPage = {
  count: 1, next: null, previous: null,
  results: [{ id: UUIDS.season, year: 2099, label: 'Synthetic fixture season', starts_on: '2099-04-01', ends_on: '2099-10-31', status: 'COMPLETE' }],
  meta,
}
const scope = {
  season: 2099, subject: 'PLAYER', subject_id: UUIDS.player, game_type: 'REGULAR',
  window: '30G', requested_n: 30, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT',
  team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE',
  actual_game_count: 17, known_eligible_game_count: 17,
}
const metrics = {
  'player.hr': valueMetric,
  'player.pa': { ...valueMetric, value: 25, unit: 'PA', numerator: 25 },
  'player.hr_per_pa': { ...valueMetric, value: 0, unit: 'HR/PA', numerator: 0, denominator: 25 },
  'player.pa_per_hr': { ...valueMetric, state: 'NOT_APPLICABLE', value: null, unit: 'PA/HR', numerator: 25, denominator: 0, reason: 'NO_HOME_RUNS_IN_SCOPE' },
  'player.hr_per_game': { ...valueMetric, value: 0, unit: 'HR/GAME', numerator: 0, denominator: 17 },
  'player.hr_game_pct': { ...valueMetric, value: 0, unit: 'PERCENT', numerator: 0, denominator: 17 },
  'player.median_hr_gap_games': { ...valueMetric, state: 'INSUFFICIENT_HISTORY', value: null, unit: 'BATTING_GAMES', numerator: null, reason: 'INSUFFICIENT_HISTORY' },
  'player.current_hr_drought_games': { ...valueMetric, value: 17, unit: 'BATTING_GAMES', numerator: 17 },
  'player.current_hr_streak_games': valueMetric,
}
const secondPlayer = { ...player, id: '77777777-7777-4777-8777-777777777777', display_name: 'Server First', represented_team: team() }
const partialPlayer = { ...player, display_name: 'Server Second' }
const leaderboard = {
  count: 2, next: '/api/v1/leaderboards/players/?page=2', previous: null,
  results: [
    { player: secondPlayer, metrics, scope: { ...scope, subject_id: secondPlayer.id }, coverage: [] },
    { player: partialPlayer, metrics: { ...metrics, 'player.hr': { ...valueMetric, state: 'INCOMPLETE', value: null, numerator: null, reason: 'SOURCE_TRUNCATED' } }, scope, coverage: [] },
  ],
  meta,
}
const discovery = { count: 1, next: null, previous: null, results: [player], meta: { ...meta, dataset_revision: '8' } }

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

function installApi({ failTeams = false }: { failTeams?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith('/api/v1/seasons/')) return json(seasonPage)
    if (url.startsWith('/api/v1/teams/')) {
      if (failTeams) return json({ error: { code: 'UNAVAILABLE', message: 'Team discovery unavailable.', details: {} }, meta: { dataset_revision: null, data_as_of: null } }, 503)
      return json({ ...seasonPage, results: [team()] })
    }
    if (url.startsWith('/api/v1/leaderboards/players/')) return json(leaderboard)
    if (url.startsWith('/api/v1/players/')) return json(discovery)
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('League vertical slice', () => {
  it('writes the default season into URL state before one leaderboard request', async () => {
    const fetchMock = installApi()
    renderApp('/league')
    expect(await screen.findByRole('heading', { name: 'League' })).toBeInTheDocument()
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/leaderboards/players/'))).toHaveLength(1))
    const requests = fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.startsWith('/api/v1/leaderboards/players/'))
    expect(requests[0]).toContain('season=2099')
  })

  it('sends URL filters, preserves server order, and delegates sorting to the server', async () => {
    const fetchMock = installApi()
    renderApp(`/league?season=2099&window=30G&team=${UUIDS.teamA}&home_away=HOME&cutoff=2099-04-03&search=Fixture&position=1B&bats=R&ordering=hr&page=1`)
    await waitFor(() => expect(screen.getByText('Server First')).toBeInTheDocument())
    const table = screen.getByRole('table', { name: 'Player analytics in server-provided order' })
    const links = within(table).getAllByRole('link')
    expect(links[0]).toHaveTextContent('Server First')
    expect(links[1]).toHaveTextContent('Server Second')
    expect(screen.queryByRole('combobox', { name: /league/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Sort by HR' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('ordering=-hr'))).toBe(true))
    const first = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => url.startsWith('/api/v1/leaderboards/players/'))!
    for (const value of ['window=30G', `team=${UUIDS.teamA}`, 'home_away=HOME', 'search=Fixture', 'position=1B', 'bats=R']) expect(first).toContain(value)
  })

  it('shows honest samples and semantic values without inventing represented teams', async () => {
    installApi()
    renderApp('/league?season=2099&window=30G')
    await waitFor(() => expect(screen.getAllByText('17 batting games available')).toHaveLength(2))
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    expect(screen.getByText('Partial data')).toBeInTheDocument()
    expect(screen.getAllByText('Not enough history')).toHaveLength(2)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Server Second' })).toHaveAttribute('href', `/players/${UUIDS.player}`)
  })

  it('keeps leaderboard and URL filters usable when team discovery fails', async () => {
    const fetchMock = installApi({ failTeams: true })
    renderApp(`/league?season=2099&team=${UUIDS.teamA}&page=1`)
    await waitFor(() => expect(screen.getByText('Server First')).toBeInTheDocument())
    expect(screen.getByText('Team options unavailable.')).toBeInTheDocument()
    expect(screen.getByLabelText('Team')).toHaveValue(UUIDS.teamA)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(screen.getByLabelText('Team')).toHaveValue(UUIDS.teamA)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('page=2') && String(url).includes(`team=${UUIDS.teamA}`))).toBe(true))
  })
})

describe('Players vertical slice', () => {
  it('keeps discovery and comparison separate with no per-row detail requests', async () => {
    const fetchMock = installApi()
    renderApp(`/players?season=2099&window=30G&team=${UUIDS.teamA}&search=Fixture&position=1B&bats=R&ordering=-hr`)
    expect(await screen.findByRole('heading', { name: 'Player discovery' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Analytical comparison' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/different revisions/i)).toBeInTheDocument())
    expect(screen.getByText('Partial data')).toBeInTheDocument()
    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    const discoveryRequest = urls.find((url) => url.startsWith('/api/v1/players/'))!
    const comparisonRequests = urls.filter((url) => url.startsWith('/api/v1/leaderboards/players/'))
    expect(discoveryRequest).not.toContain('window=')
    expect(discoveryRequest).not.toContain('ordering=')
    expect(comparisonRequests).toHaveLength(1)
    expect(urls.some((url) => /\/api\/v1\/players\/[0-9a-f-]+\//.test(url))).toBe(false)
    expect(screen.getAllByRole('link', { name: 'Fixture Slugger' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('columnheader', { name: /Games with HR/ })).toBeInTheDocument()
  })
})
