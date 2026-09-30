import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createTeamRecurrenceBenchmark } from '@/benchmarks/teamRecurrenceBenchmark'
import { meta, UUIDS } from '@/test/fixtures'
import { renderApp } from '@/test/renderApp'

const seasonPage = {
  count: 1, next: null, previous: null,
  results: [{ id: UUIDS.season, year: 2099, label: 'Synthetic 2099', starts_on: '2099-04-01', ends_on: '2099-10-31', status: 'COMPLETE' }],
  meta,
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

function installApi(response = createTeamRecurrenceBenchmark(3, 7)) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith('/api/v1/seasons/')) return json(seasonPage)
    if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/recurrence/`)) return json(response)
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('Team recurrence matrix', () => {
  it('canonicalizes missing season and the visible default 30G before one recurrence request', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}/recurrence`)
    expect(await screen.findByRole('heading', { name: 'Benchmark Club recurrence' })).toBeInTheDocument()
    const recurrence = fetchMock.mock.calls.filter(([url]) => String(url).includes('/recurrence/'))
    expect(recurrence).toHaveLength(1)
    expect(String(recurrence[0][0])).toContain('season=2099')
    expect(String(recurrence[0][0])).toContain('window=30G')
  })

  it('maps analytical URL scope but never sends presentation row order', async () => {
    const fetchMock = installApi()
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=7G&home_away=AWAY&cutoff=2099-05-01&row_order=name`)
    await screen.findByRole('heading', { name: 'Benchmark Club recurrence' })
    const url = String(fetchMock.mock.calls.find(([value]) => String(value).includes('/recurrence/'))?.[0])
    for (const value of ['season=2099', 'window=7G', 'home_away=AWAY', 'cutoff=2099-05-01']) expect(url).toContain(value)
    expect(url).not.toContain('row_order')
  })

  it('renders every cell state explicitly without turning semantic nulls into zero', async () => {
    installApi(createTeamRecurrenceBenchmark(1, 7))
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`)
    const table = await screen.findByRole('table', { name: /home-run recurrence matrix/i })
    for (const text of ['2', '0', 'DNP', '0 PA', 'Not with team', '?', 'Partial']) {
      expect(within(table).getAllByText(text).length).toBeGreaterThan(0)
    }
  })

  it('makes every event in a multi-HR cell reachable with return context', async () => {
    const response = createTeamRecurrenceBenchmark(1, 1)
    installApi(response)
    const route = `/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`
    renderApp(route)
    const table = await screen.findByRole('table', { name: /home-run recurrence matrix/i })
    const cell = within(table).getByLabelText(/Benchmark Player 01, representing Benchmark Club.*2 home runs/)
    fireEvent.click(cell)
    const eventIds = response.rows[0].cells[0].state === 'HR_COUNT' ? response.rows[0].cells[0].home_run_event_ids : []
    for (const [index, eventId] of eventIds.entries()) {
      const link = within(table).getByRole('link', { name: `HR ${index + 1}` })
      expect(link).toHaveAttribute('href', `/games/${response.columns[0].game_id}#hr-${eventId}`)
    }
  })

  it('supports roving directional, Home/End, action, and Escape keyboard behavior', async () => {
    installApi(createTeamRecurrenceBenchmark(2, 3))
    const { container } = renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`)
    await screen.findByRole('table', { name: /home-run recurrence matrix/i })
    const cell = (row: number, column: number) => container.querySelector<HTMLElement>(`[data-matrix-row="${row}"][data-matrix-column="${column}"]`)!
    cell(0, 0).focus()
    fireEvent.keyDown(cell(0, 0), { key: 'ArrowRight' }); await waitFor(() => expect(cell(0, 1)).toHaveFocus())
    fireEvent.keyDown(cell(0, 1), { key: 'ArrowDown' }); await waitFor(() => expect(cell(1, 1)).toHaveFocus())
    fireEvent.keyDown(cell(1, 1), { key: 'Home' }); await waitFor(() => expect(cell(1, 0)).toHaveFocus())
    fireEvent.keyDown(cell(1, 0), { key: 'End' }); await waitFor(() => expect(cell(1, 2)).toHaveFocus())
    fireEvent.keyDown(cell(1, 2), { key: 'ArrowUp' }); await waitFor(() => expect(cell(0, 2)).toHaveFocus())
    fireEvent.keyDown(cell(0, 2), { key: 'ArrowLeft' }); await waitFor(() => expect(cell(0, 1)).toHaveFocus())
    cell(0, 0).focus(); fireEvent.keyDown(cell(0, 0), { key: 'Enter' })
    const detailLink = (await screen.findAllByRole('link', { name: 'HR 1' }))[0]
    await waitFor(() => expect(detailLink).toHaveFocus())
    fireEvent.keyDown(detailLink, { key: 'Escape' })
    expect(cell(0, 0)).toHaveFocus()
    fireEvent.keyDown(cell(0, 0), { key: ' ' })
    await waitFor(() => expect(within(screen.getByRole('table', { name: /home-run recurrence matrix/i })).getByRole('link', { name: 'HR 1' })).toHaveFocus())
  })

  it('orders whole rows by server metrics with unavailable rows last and stable IDs', async () => {
    const response = createTeamRecurrenceBenchmark(3, 2)
    response.rows[0].player_season_hr = { ...response.rows[0].player_season_hr, state: 'UNKNOWN', value: null, numerator: null }
    installApi(response)
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`)
    const table = await screen.findByRole('table', { name: /home-run recurrence matrix/i })
    const names = within(table).getAllByRole('rowheader').map((header) => header.textContent)
    expect(names.at(-1)).toContain('Benchmark Player 01')
    fireEvent.change(screen.getByRole('combobox', { name: 'Row order' }), { target: { value: 'name' } })
    await waitFor(() => expect(within(table).getAllByRole('rowheader')[0]).toHaveTextContent('Benchmark Player 01'))
  })

  it('shows unresolved membership and its lower bound without a fake matrix', async () => {
    const response = createTeamRecurrenceBenchmark(0, 0)
    response.scope.selection_state = 'ORDER_UNVERIFIED'
    response.scope.actual_game_count = null
    response.scope.known_eligible_game_count = 17
    installApi(response)
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`)
    expect(await screen.findByRole('heading', { name: 'Matrix membership is not definitive' })).toBeInTheDocument()
    expect(screen.getByText(/At least 17 eligible games/)).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: /home-run recurrence matrix/i })).not.toBeInTheDocument()
    expect(screen.getByText(/Data as of/)).toBeInTheDocument()
  })

  it('provides a complete player-selectable mobile sequence with every game and HR link', async () => {
    const response = createTeamRecurrenceBenchmark(2, 7)
    installApi(response)
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G`)
    const region = await screen.findByRole('region', { name: 'Player game sequence' })
    expect(within(region).getAllByRole('option')).toHaveLength(2)
    expect(within(region).getAllByRole('listitem')).toHaveLength(7)
    expect(within(region).getAllByRole('link', { name: /^HR / }).length).toBeGreaterThan(1)
    fireEvent.change(within(region).getByRole('combobox', { name: 'Player' }), { target: { value: response.rows[1].player.id } })
    expect(within(region).getByRole('combobox', { name: 'Player' })).toHaveValue(response.rows[1].player.id)
    expect(within(region).getAllByRole('listitem')).toHaveLength(7)
  })

  it('rejects unsupported recurrence URL state visibly', async () => {
    installApi()
    renderApp(`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G&page=2`)
    expect(await screen.findByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
  })
})
