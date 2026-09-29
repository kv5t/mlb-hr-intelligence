import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { game, meta, player, team, UUIDS, valueMetric } from '@/test/fixtures'
import { renderApp } from '@/test/renderApp'

const seasonPage = { count: 1, next: null, previous: null, results: [{ id: UUIDS.season, year: 2099, label: 'Synthetic 2099', starts_on: '2099-04-01', ends_on: '2099-10-31', status: 'COMPLETE' }], meta }
const teamPage = { count: 1, next: null, previous: null, results: [team()], meta }
const scope = { season: 2099, subject: 'TEAM', subject_id: UUIDS.teamA, game_type: 'REGULAR', window: '7G', requested_n: 7, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT', team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE', actual_game_count: 1, known_eligible_game_count: 1 }
const metricNames = ['hr', 'pa', 'hr_per_pa', 'pa_per_hr', 'hr_per_game', 'hr_games', 'hr_game_pct', 'multi_hr_games', 'avg_hr_gap_games', 'median_hr_gap_games', 'current_hr_drought_games', 'max_hr_drought_games', 'current_hr_streak_games', 'max_hr_streak_games']
const teamMetrics = Object.fromEntries(metricNames.map((name) => [`team.${name}`, valueMetric]))
const detail = { team: team(), metrics: { ...teamMetrics, 'team.hr': { ...valueMetric, value: 2, numerator: 2 }, 'team.current_hr_drought_games': { ...valueMetric, value: 11, unit: 'TEAM_GAMES', numerator: 11 } }, scope, coverage: [{ domain: 'HR_EVENTS', state: 'COMPLETE', reason_codes: [] }], meta }
const playerMetrics = { 'player.hr': valueMetric, 'player.pa': valueMetric, 'player.hr_per_pa': valueMetric, 'player.pa_per_hr': valueMetric, 'player.hr_per_game': valueMetric, 'player.hr_game_pct': valueMetric, 'player.median_hr_gap_games': { ...valueMetric, state: 'INSUFFICIENT_HISTORY', value: null, reason: 'INSUFFICIENT_HISTORY' }, 'player.current_hr_drought_games': valueMetric }
const playerScope = { ...scope, subject: 'PLAYER', subject_id: UUIDS.player, team_filter_id: UUIDS.teamA, actual_game_count: 1 }
const event = { id: '88888888-8888-4888-8888-888888888888', game_id: UUIDS.game, plate_appearance_id: '99999999-9999-4999-8999-999999999999', official_date: '2099-04-03', batter: player, pitcher: null, batting_team: team(), inning: 4, half_inning: 'BOTTOM', game_pa_ordinal: 10, provenance: { source_label: 'SYNTHETIC', retrieved_at: meta.data_as_of } }

function json(payload: unknown, status = 200) { return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } }) }

function installApi(options: { playerFailure?: boolean; hrPartial?: boolean; detailMissing?: boolean; hrFailure?: boolean; discoveryNext?: boolean; comparisonNext?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/home-runs/`)) {
      if (options.hrFailure) return json({ error: { code: 'UNAVAILABLE', message: 'HR log unavailable', details: {} }, meta: { dataset_revision: null, data_as_of: null } }, 503)
      return json({ count: 1, next: '/api/v1/teams/x/home-runs/?page=2', previous: null, results: [event], team: team(), total_hr: options.hrPartial ? { ...valueMetric, state: 'INCOMPLETE', value: null, numerator: null, reason: 'SOURCE_TRUNCATED' } : { ...valueMetric, value: 2, numerator: 2 }, scope, coverage: [], meta })
    }
    if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/`)) {
      if (options.detailMissing) return json({ error: { code: 'NOT_FOUND', message: 'Not found.', details: {} }, meta }, 404)
      return json(detail)
    }
    if (url.startsWith('/api/v1/seasons/')) return json(seasonPage)
    if (url.startsWith('/api/v1/teams/')) return json(teamPage)
    if (url.startsWith('/api/v1/players/')) {
      if (options.playerFailure) return json({ error: { code: 'UNAVAILABLE', message: 'Discovery unavailable', details: {} }, meta: { dataset_revision: null, data_as_of: null } }, 503)
      return json({ count: 1, next: options.discoveryNext ? '/api/v1/players/?page=2' : null, previous: null, results: [player], meta: { ...meta, dataset_revision: '8' } })
    }
    if (url.startsWith('/api/v1/leaderboards/players/')) return json({ count: 1, next: options.comparisonNext ? '/api/v1/leaderboards/players/?page=2' : null, previous: null, results: [{ player, metrics: playerMetrics, scope: playerScope, coverage: [] }], meta })
    if (url.startsWith('/api/v1/games/')) return json({ count: 1, next: null, previous: null, results: [game], meta })
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('Teams vertical slice', () => {
  it('uses server discovery filters and preserves season on detail links', async () => {
    const fetchMock = installApi()
    renderApp('/teams?season=2099&league=Synthetic&division=East&search=Team&ordering=-name&page=1')
    const link = await screen.findByRole('link', { name: 'Synthetic Team' })
    expect(link).toHaveAttribute('href', `/teams/${UUIDS.teamA}?season=2099`)
    const request = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => url.startsWith('/api/v1/teams/?'))!
    for (const value of ['season=2099', 'league=Synthetic', 'division=East', 'search=Team', 'ordering=-name']) expect(request).toContain(value)
  })

  it('rejects unsupported URL state visibly', async () => {
    installApi()
    renderApp('/teams?window=7G')
    expect(await screen.findByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
  })
})

describe('Team Detail vertical slice', () => {
  it('writes a missing season, renders overview semantics, and does not eagerly fetch tab data', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}`)
    expect(await screen.findByRole('heading', { name: 'Synthetic Team' })).toBeInTheDocument()
    expect(screen.getByText('11')).toBeInTheDocument()
    expect(screen.getByText(/1 team game available/)).toBeInTheDocument()
    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(urls.filter((url) => url.startsWith(`/api/v1/teams/${UUIDS.teamA}/`))).toHaveLength(1)
    expect(urls.some((url) => url.startsWith('/api/v1/players/'))).toBe(false)
    expect(urls.some((url) => url.startsWith('/api/v1/games/'))).toBe(false)
    expect(screen.getByRole('link', { name: 'Open team recurrence matrix' })).toHaveAttribute(
      'href',
      `/teams/${UUIDS.teamA}/recurrence?cutoff=2099-04-03&home_away=ALL&season=2099&window=7G`,
    )
  })

  it('loads Players independently, labels association honestly, and keeps detail on panel failure', async () => {
    installApi({ playerFailure: true })
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=players`)
    expect(await screen.findByText(/not a complete historical roster/i)).toBeInTheDocument()
    expect(screen.getByText('Service temporarily unavailable')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Synthetic Team' })).toBeInTheDocument()
  })

  it('keeps separately revised player panels distinct and links their own identities', async () => {
    const fetchMock = installApi({ discoveryNext: true, comparisonNext: true })
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=players`)
    expect(await screen.findByText(/different dataset revisions/i)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Fixture Slugger' }).length).toBeGreaterThan(0)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/players/'))).toHaveLength(1)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/leaderboards/players/'))).toHaveLength(1)
    expect(fetchMock.mock.calls.some(([url]) => /\/api\/v1\/players\/[0-9a-f-]+\//.test(String(url)))).toBe(false)
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Team player discovery pagination' })).getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith('/api/v1/players/') && String(url).includes('page=2'))).toBe(true))
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/leaderboards/players/')).every(([url]) => !String(url).includes('page=2'))).toBe(true)
  })

  it('keeps schedule pagination separate and does not forward analytical filters', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}?season=2099&window=7G&home_away=HOME&cutoff=2099-04-03&tab=games&games_page=2`)
    expect(await screen.findByRole('heading', { name: 'Games' })).toBeInTheDocument()
    const request = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => url.startsWith('/api/v1/games/'))!
    expect(request).toContain(`team=${UUIDS.teamA}`)
    expect(request).toContain('page=2')
    expect(request).not.toContain('window=')
    expect(request).not.toContain('home_away=')
    expect(screen.getByRole('link', { name: '2099-04-03' })).toHaveAttribute('href', `/games/${UUIDS.game}`)
  })

  it('distinguishes verified event record count from a partial authoritative total', async () => {
    const fetchMock = installApi({ hrPartial: true })
    renderApp(`/teams/${UUIDS.teamA}?season=2099&window=7G&home_away=AWAY&tab=hr-log`)
    expect(await screen.findByText('Partial data')).toBeInTheDocument()
    expect(screen.getByText(/1 verified event records/)).toBeInTheDocument()
    expect(screen.getByText('Unknown pitcher')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open game' })).toHaveAttribute('href', `/games/${UUIDS.game}#hr-${event.id}`)
    const request = fetchMock.mock.calls.map(([url]) => String(url)).find((url) => url.startsWith(`/api/v1/teams/${UUIDS.teamA}/home-runs/`))!
    expect(request).toContain('home_away=AWAY')
    expect(request).toContain('ordering=official_date')
  })

  it('resets HR pagination when an analytical filter changes', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=hr-log&hr_page=3`)
    await screen.findByRole('heading', { name: 'HR Log' })
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/home-runs/') && String(url).includes('page=3'))).toBe(true)
    fireEvent.change(screen.getByRole('combobox', { name: 'Home / away' }), { target: { value: 'HOME' } })
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/home-runs/') && String(url).includes('home_away=HOME') && String(url).includes('page=1'))).toBe(true))
  })

  it('maps HR event order from URL state and resets only HR pagination', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=hr-log&hr_ordering=-official_date&hr_page=3`)
    const order = await screen.findByRole('combobox', { name: 'Event order' })
    expect(order).toHaveValue('-official_date')
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/home-runs/') && String(url).includes('ordering=-official_date') && String(url).includes('page=3'))).toBe(true)
    fireEvent.change(order, { target: { value: 'official_date' } })
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/home-runs/') && String(url).includes('ordering=official_date') && String(url).includes('page=1'))).toBe(true))
  })

  it('keeps the base Team resource visible when HR Log fails', async () => {
    installApi({ hrFailure: true })
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=hr-log`)
    expect(await screen.findByText('Service temporarily unavailable')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Synthetic Team' })).toBeInTheDocument()
  })

  it('renders a missing canonical Team as a resource error', async () => {
    installApi({ detailMissing: true })
    renderApp(`/teams/${UUIDS.teamA}?season=2099`)
    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Team detail sections' })).not.toBeInTheDocument()
  })

  it('rejects garbage tabs instead of changing scope', async () => {
    installApi()
    renderApp(`/teams/${UUIDS.teamA}?season=2099&tab=recurrence`)
    expect(await screen.findByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
  })
})
