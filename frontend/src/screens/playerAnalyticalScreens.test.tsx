import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '@/test/renderApp'
import { playerDetail, playerRecurrence, playerHomeRuns, analyticalSeasonPage } from '@/test/playerAnalyticalFixtures'
import { UUIDS, team, valueMetric, meta, game } from '@/test/fixtures'

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }) }
function install({ detail = playerDetail, recurrence = playerRecurrence, log = playerHomeRuns, failTeams = false, failLog = false }: { detail?: unknown; recurrence?: unknown; log?: unknown; failTeams?: boolean; failLog?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith(`/api/v1/games/${UUIDS.game}/`)) return json({ game, participants: [], home_runs: playerHomeRuns.results, coverage: [], meta })
    if (url.startsWith('/api/v1/seasons/')) return json(analyticalSeasonPage)
    if (url.startsWith('/api/v1/teams/')) return failTeams ? json({ error: { code: 'UNAVAILABLE', message: 'Options unavailable', details: {} }, meta }, 503) : json({ ...analyticalSeasonPage, results: [team()] })
    if (url.startsWith(`/api/v1/players/${UUIDS.player}/recurrence/`)) return json(recurrence)
    if (url.startsWith(`/api/v1/players/${UUIDS.player}/home-runs/`)) return failLog ? json({ error: { code: 'UNAVAILABLE', message: 'Please retry', details: {} }, meta }, 503) : json(log)
    if (url.startsWith(`/api/v1/players/${UUIDS.player}/`)) return json(detail)
    throw new Error(`Unexpected request ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock); return fetchMock
}
afterEach(() => vi.unstubAllGlobals())
const route = `/players/${UUIDS.player}`
const analytics = (mock: ReturnType<typeof install>) => mock.mock.calls.map(([url]) => String(url)).filter((url) => url.startsWith(`/api/v1/players/${UUIDS.player}/`))

describe('B20 Player detail', () => {
  it('writes season and SEASON default before one analytical request', async () => {
    const fetchMock = install(); renderApp(route)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Overview' })
    expect(analytics(fetchMock)).toHaveLength(1); expect(analytics(fetchMock)[0]).toContain('season=2099'); expect(analytics(fetchMock)[0]).toContain('window=SEASON')
  })
  it('shows server semantic metrics, honest sample and unclamped current drought', async () => {
    const detail = structuredClone(playerDetail)
    Object.assign(detail.metrics['player.pa'], { state: 'UNKNOWN', value: null, numerator: null })
    Object.assign(detail.metrics['player.hr_per_pa'], { state: 'INCOMPLETE', value: null, numerator: null })
    install({ detail }); renderApp(`${route}?season=2099&window=7G`)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Overview' })
    expect(screen.getByLabelText('HR: 0 HR')).toBeInTheDocument()
    expect(screen.getByText('Unknown')).toBeInTheDocument(); expect(screen.getByText('Partial data')).toBeInTheDocument()
    expect(screen.getByLabelText('Current HR Drought — Batting Games: 11 BATTING_GAMES')).toBeInTheDocument()
    expect(screen.getByText(/3 batting games available/)).toBeInTheDocument(); expect(screen.getByText(/Data as of/)).toBeInTheDocument(); expect(screen.getByText('HR EVENTS: COMPLETE')).toBeInTheDocument()
    expect(screen.queryByText(/Evidenced represented team/)).not.toBeInTheDocument()
  })
  it('shows representation only from response and preserves supported scope in section links', async () => {
    install({ detail: { ...playerDetail, player: { ...playerDetail.player, represented_team: team() } } })
    renderApp(`${route}?season=2099&window=7G&team=${UUIDS.teamA}&home_away=AWAY&cutoff=2099-04-03`)
    expect(await screen.findByText(/Evidenced represented team/)).toBeInTheDocument()
    for (const label of ['Recurrence', 'Home Runs']) {
      const href = screen.getByRole('link', { name: label }).getAttribute('href')!
      for (const value of ['season=2099', 'window=7G', `team=${UUIDS.teamA}`, 'home_away=AWAY', 'cutoff=2099-04-03']) expect(href).toContain(value)
    }
  })
  it('keeps requested team and usable analytics during auxiliary discovery failure', async () => {
    const fetchMock = install({ failTeams: true }); renderApp(`${route}?season=2099&window=7G&team=${UUIDS.teamB}`)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Overview' })
    expect(await screen.findByText(/Team options unavailable/)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /Team scope/ })).toHaveValue(UUIDS.teamB)
    fireEvent.click(screen.getByRole('button', { name: 'Retry team options' }))
    expect(analytics(fetchMock)).toHaveLength(1); expect(analytics(fetchMock)[0]).toContain(`team=${UUIDS.teamB}`)
  })
  it.each(['season=0000', 'season=2099&team=bad', 'season=2099&season=2098', 'season=2099&search=x'])('rejects invalid URL %s before analytics', async (query) => {
    const fetchMock = install(); renderApp(`${route}?${query}`)
    expect(await screen.findByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument(); expect(analytics(fetchMock)).toHaveLength(0)
  })
  it('shows malformed resource UUID as not found without an analytical request', async () => {
    const fetchMock = install(); renderApp('/players/bad?season=2099')
    expect(await screen.findByRole('heading', { name: 'Not found' })).toBeInTheDocument(); expect(analytics(fetchMock)).toHaveLength(0)
  })
})

describe('B20 Player recurrence', () => {
  it('uses explicit 30G default and one recurrence request with correct scope', async () => {
    const fetchMock = install(); renderApp(`${route}/recurrence?season=2099&team=${UUIDS.teamA}&home_away=HOME&cutoff=2099-04-03`)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Recurrence' })
    expect(analytics(fetchMock)).toHaveLength(1)
    for (const value of ['/recurrence/', 'window=30G', `team=${UUIDS.teamA}`, 'home_away=HOME', 'cutoff=2099-04-03']) expect(analytics(fetchMock)[0]).toContain(value)
  })
  it('preserves server observation order, per-game teams, zero and multi-HR, and exact public gaps', async () => {
    install(); renderApp(`${route}/recurrence?season=2099&window=7G`)
    const table = await screen.findByRole('table', { name: /Chronological player batting games/ })
    expect(within(table).getAllByRole('rowheader').map((row) => row.textContent)).toEqual(['2099-04-02', '2099-04-01'])
    expect(within(table).getByText('Historical B')).toBeInTheDocument()
    expect(within(table).getByLabelText('2099-04-02 HR: 0 HR')).toBeInTheDocument(); expect(within(table).getByLabelText('2099-04-01 HR: 2 HR')).toBeInTheDocument()
    expect(screen.getByLabelText('Gap 1 non-HR batting games: 0 BATTING_GAMES')).toBeInTheDocument(); expect(screen.getByLabelText('Gap 2 non-HR batting games: 2 BATTING_GAMES')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Gap 1 start game' })).toHaveAttribute('href', `/games/${playerRecurrence.gaps[0].from_game_id}`)
    expect(screen.getByRole('heading', { name: 'Chronological HR strip' })).toBeInTheDocument()
  })
  it('shows unknown/partial observations without converting either to zero', async () => {
    const recurrence = structuredClone(playerRecurrence)
    Object.assign(recurrence.observations[0].hr, { state: 'UNKNOWN', value: null, numerator: null })
    Object.assign(recurrence.observations[1].hr, { state: 'INCOMPLETE', value: null, numerator: null })
    install({ recurrence }); renderApp(`${route}/recurrence?season=2099&window=30G`)
    const table = await screen.findByRole('table', { name: /Chronological player batting games/ })
    expect(within(table).getByText('Unknown')).toBeInTheDocument(); expect(within(table).getByText('Partial data')).toBeInTheDocument()
  })
  it('does not fabricate an unresolved timeline and shows coverage/freshness', async () => {
    const recurrence = { ...playerRecurrence, observations: [], gaps: [], scope: { ...playerRecurrence.scope, selection_state: 'UNKNOWN', actual_game_count: null } }
    install({ recurrence }); renderApp(`${route}/recurrence?season=2099&window=30G`)
    expect(await screen.findByText(/Batting-game membership is unresolved/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Chronological HR strip' })).not.toBeInTheDocument(); expect(screen.getByText(/Data as of/)).toBeInTheDocument()
  })
  it('changes scope without fetching per-game resources and restores the section scope through navigation', async () => {
    const fetchMock = install(); renderApp(`${route}/recurrence?season=2099&window=30G`)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Recurrence' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Window' }), { target: { value: '7G' } })
    await waitFor(() => expect(analytics(fetchMock)).toHaveLength(2))
    expect(analytics(fetchMock)[1]).toContain('window=7G')
    fireEvent.click(await screen.findByRole('link', { name: 'Overview' }))
    await screen.findByRole('heading', { name: 'Fixture Slugger · Overview' })
    expect(analytics(fetchMock).at(-1)).toContain('window=7G')
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith('/api/v1/games/'))).toBe(false)
  })
})

describe('B20 Player HR log', () => {
  it('defaults to 30G/oldest first and separates known-event count from partial total', async () => {
    const fetchMock = install(); renderApp(`${route}/home-runs?season=2099`)
    expect(await screen.findByText(/3 verified event records/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Player home-run total: Partial data/)).toBeInTheDocument()
    expect(analytics(fetchMock)).toHaveLength(1); expect(analytics(fetchMock)[0]).toContain('window=30G'); expect(analytics(fetchMock)[0]).toContain('ordering=official_date')
    expect(screen.getAllByText(/Unknown pitcher/)).toHaveLength(2)
    expect(screen.getAllByText(/Synthetic public evidence/)).toHaveLength(2)
    expect(screen.getAllByRole('link', { name: 'Open home run in game' })[0]).toHaveAttribute('href', `/games/${UUIDS.game}#hr-${playerHomeRuns.results[0].id}`)
  })
  it('preserves return scope through a focused Game Detail event link', async () => {
    install(); const source = `${route}/home-runs?season=2099&window=7G&hr_page=2&hr_ordering=-official_date`
    renderApp(source)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Home Runs' })
    fireEvent.click(screen.getAllByRole('link', { name: 'Open home run in game' })[0])
    const back = await screen.findByRole('link', { name: '← Back' })
    expect(back).toHaveAttribute('href', source)
    expect(screen.getByText('Requested event')).toBeInTheDocument()
    fireEvent.click(back)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Home Runs' })
    expect(screen.getByRole('combobox', { name: 'Event order' })).toHaveValue('-official_date')
    expect(screen.getByText(/Page 2/)).toBeInTheDocument()
  })
  it('maps independent HR page and resets it when event ordering changes', async () => {
    const fetchMock = install(); renderApp(`${route}/home-runs?season=2099&window=30G&hr_page=3&team=${UUIDS.teamA}`)
    await screen.findByRole('heading', { name: 'Fixture Slugger · Home Runs' })
    expect(analytics(fetchMock)[0]).toContain('page=3'); expect(analytics(fetchMock)[0]).not.toContain('hr_page')
    fireEvent.change(screen.getByRole('combobox', { name: 'Event order' }), { target: { value: '-official_date' } })
    await waitFor(() => expect(analytics(fetchMock)).toHaveLength(2))
    expect(analytics(fetchMock)[1]).toContain('ordering=-official_date'); expect(analytics(fetchMock)[1]).toContain('page=1'); expect(analytics(fetchMock)[1]).toContain(`team=${UUIDS.teamA}`)
    fireEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await waitFor(() => expect(analytics(fetchMock)).toHaveLength(3)); expect(analytics(fetchMock)[2]).toContain('page=2')
    expect((await screen.findByRole('link', { name: 'Overview' })).getAttribute('href')).not.toContain('hr_')
  })
  it.each(['VALUE', 'UNKNOWN'])('preserves %s total with a valid empty list', async (state) => {
    const log = { ...playerHomeRuns, count: 0, next: null, results: [], total_hr: { ...valueMetric, state, value: state === 'VALUE' ? 0 : null } }
    install({ log }); renderApp(`${route}/home-runs?season=2099&window=30G`)
    expect(await screen.findByText(/No verified player home-run events/)).toBeInTheDocument()
    expect(screen.getByLabelText(`Player home-run total: ${state === 'VALUE' ? '0' : 'Unknown'} HR`)).toBeInTheDocument()
  })
  it('retries a 503 without changing requested scope', async () => {
    const fetchMock = install({ failLog: true }); renderApp(`${route}/home-runs?season=2099&window=7G&cutoff=2099-04-03`)
    expect(await screen.findByRole('heading', { name: 'Service temporarily unavailable' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(analytics(fetchMock)).toHaveLength(2)); expect(analytics(fetchMock)[0]).toBe(analytics(fetchMock)[1])
  })
})
