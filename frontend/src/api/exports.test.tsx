import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadExport, exportRequest, type ExportKind } from './exports'
import { ExportActions } from '@/components/ExportActions'
import { renderApp } from '@/test/renderApp'
import { createTeamRecurrenceBenchmark } from '@/benchmarks/teamRecurrenceBenchmark'
import { UUIDS, meta, team } from '@/test/fixtures'
import { playerDetail, playerRecurrence, playerHomeRuns, analyticalSeasonPage } from '@/test/playerAnalyticalFixtures'

const createUrl = vi.fn(() => 'blob:export-test')
const revokeUrl = vi.fn()
const filenames: string[] = []
beforeEach(() => {
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createUrl; static revokeObjectURL = revokeUrl })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { filenames.push(this.download) })
  createUrl.mockClear(); revokeUrl.mockClear(); filenames.length = 0
})
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
const file = (format: 'csv' | 'pdf' = 'csv') => new Response(format === 'pdf' ? '%PDF-example' : 'state,value\r\nVALUE,0\r\n', { headers: { 'Content-Type': format === 'pdf' ? 'application/pdf' : 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="server-report.${format}"`, 'X-Dataset-Revision': '7' } })
const error = { error: { code: 'REVISION_UNAVAILABLE', message: 'Please retry export', details: {} }, meta }
const kinds: ExportKind[] = ['leaderboard', 'teamRecurrence', 'playerRecurrence', 'teamHomeRuns', 'playerHomeRuns']

describe('B21 binary export boundary', () => {
  it.each(kinds)('normalizes full-view scope for %s and strips pagination/presentation', async (kind) => {
    const params = { season: 2099, window: '30G', cutoff: '2099-04-03', home_away: 'AWAY', team: UUIDS.teamB, ordering: '-official_date', page: 3, page_size: 25, hr_page: 2, row_order: 'name', dataset_revision: '8', search: 'Slugger' }
    if (kind === 'leaderboard') params.ordering = '-hr'
    const request = exportRequest({ kind, id: UUIDS.player, params }, 'csv')
    const query = new URL(request.url, 'http://test').searchParams
    for (const key of ['page', 'page_size', 'hr_page', 'row_order', 'dataset_revision']) expect(query.has(key)).toBe(false)
    expect(query.get('format')).toBe('csv'); expect(query.get('cutoff')).toBe('2099-04-03'); expect(query.get('home_away')).toBe('AWAY')
    if (kind.startsWith('team')) expect(query.has('team')).toBe(false)
    const fetchMock = vi.fn(async () => file()); vi.stubGlobal('fetch', fetchMock)
    await downloadExport({ kind, id: UUIDS.player, params }, 'csv')
    expect(fetchMock).toHaveBeenCalledWith(request.url, expect.objectContaining({ headers: { Accept: 'text/csv' } }))
    expect(filenames).toEqual(['server-report.csv']); expect(createUrl).toHaveBeenCalledTimes(1); expect(revokeUrl).toHaveBeenCalledWith('blob:export-test')
  })
  it('downloads PDF bytes and uses a safe fallback for unsafe filenames', async () => {
    const response = file('pdf'); response.headers.set('Content-Disposition', 'attachment; filename="../../bad.pdf"')
    vi.stubGlobal('fetch', vi.fn(async () => response))
    await downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'pdf')
    expect(filenames).toEqual(['mlb-leaderboard.pdf'])
  })
  it.each([400, 404, 503])('does not download JSON HTTP %s and preserves public errors', async (status) => {
    vi.stubGlobal('fetch', vi.fn(async () => json(error, status)))
    await expect(downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'csv')).rejects.toMatchObject({ kind: 'api', status, code: error.error.code, meta })
    expect(createUrl).not.toHaveBeenCalled()
  })
  it('distinguishes network, malformed errors and unexpected successful content', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    await expect(downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'csv')).rejects.toMatchObject({ kind: 'network' })
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>error</html>', { status: 503 })))
    await expect(downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'csv')).rejects.toMatchObject({ code: 'INVALID_ERROR_RESPONSE' })
    vi.stubGlobal('fetch', vi.fn(async () => json(error)))
    await expect(downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'pdf')).rejects.toMatchObject({ code: 'INVALID_EXPORT_CONTENT' })
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { headers: { 'Content-Type': 'application/pdf' } })))
    await expect(downloadExport({ kind: 'leaderboard', params: { season: 2099 } }, 'pdf')).rejects.toMatchObject({ code: 'INVALID_EXPORT_CONTENT' })
    expect(createUrl).not.toHaveBeenCalled()
  })
  it('prevents concurrent duplicate clicks and keeps the ordinary screen usable', async () => {
    let finish!: (response: Response) => void
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => { finish = resolve })); vi.stubGlobal('fetch', fetchMock)
    render(<><h1>Analytical content</h1><ExportActions target={{ kind: 'leaderboard', params: { season: 2099 } }} /></>)
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    fireEvent.click(screen.getByRole('button', { name: 'Preparing CSV…' }))
    expect(screen.getByRole('button', { name: 'Preparing CSV…' })).toBeDisabled(); expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('heading', { name: 'Analytical content' })).toBeInTheDocument()
    finish(file()); await screen.findByText(/Downloaded server-report.csv/)
  })
  it('retries a 503 export without changing scope', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(error, 503)).mockResolvedValueOnce(file()); vi.stubGlobal('fetch', fetchMock)
    render(<ExportActions target={{ kind: 'playerHomeRuns', id: UUIDS.player, params: { season: 2099, window: '7G', cutoff: '2099-04-03' } }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' })); await screen.findByRole('heading', { name: 'Service temporarily unavailable' })
    fireEvent.click(screen.getByRole('button', { name: 'Retry' })); await screen.findByText(/Downloaded server-report.csv/)
    expect(fetchMock.mock.calls[0][0]).toBe(fetchMock.mock.calls[1][0]); expect(filenames).toHaveLength(1)
  })
})

describe('B21 export actions on all five screens', () => {
  it.each([
    ['/league?season=2099&window=30G&ordering=-hr&page=2', 'leaderboards/players/'],
    [`/teams/${UUIDS.teamA}/recurrence?season=2099&window=30G&row_order=name`, `teams/${UUIDS.teamA}/recurrence/`],
    [`/players/${UUIDS.player}/recurrence?season=2099&window=30G&team=${UUIDS.teamB}`, `players/${UUIDS.player}/recurrence/`],
    [`/teams/${UUIDS.teamA}?season=2099&tab=hr-log&hr_page=2&hr_ordering=-official_date`, `teams/${UUIDS.teamA}/home-runs/`],
    [`/players/${UUIDS.player}/home-runs?season=2099&window=30G&hr_page=2&hr_ordering=-official_date`, `players/${UUIDS.player}/home-runs/`],
  ])('wires CSV/PDF actions from %s to the server contract', async (route, path) => {
    const matrix = createTeamRecurrenceBenchmark(1, 1)
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.startsWith('/api/v1/exports/')) return file(new URL(url, 'http://test').searchParams.get('format') === 'pdf' ? 'pdf' : 'csv')
      if (url.startsWith('/api/v1/seasons/')) return json(analyticalSeasonPage)
      if (url.startsWith('/api/v1/leaderboards/')) return json({ count: 1, next: null, previous: null, results: [playerDetail], meta })
      if (url.startsWith(`/api/v1/players/${UUIDS.player}/recurrence/`)) return json(playerRecurrence)
      if (url.startsWith(`/api/v1/players/${UUIDS.player}/home-runs/`)) return json(playerHomeRuns)
      if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/recurrence/`)) return json(matrix)
      if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/home-runs/`)) return json({ ...playerHomeRuns, team: matrix.team, scope: matrix.scope })
      if (url.startsWith(`/api/v1/teams/${UUIDS.teamA}/`)) return json(matrix)
      if (url.startsWith('/api/v1/teams/')) return json({ ...analyticalSeasonPage, results: [team()] })
      throw new Error(`Unexpected request ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock); renderApp(route)
    fireEvent.click(await screen.findByRole('button', { name: 'Export CSV' })); await screen.findByText(/Downloaded server-report.csv/)
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' })); await screen.findByText(/Downloaded server-report.pdf/)
    const calls = fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.startsWith('/api/v1/exports/'))
    expect(calls).toHaveLength(2)
    for (const url of calls) {
      expect(url).toContain(`/api/v1/exports/${path}?`)
      const query = new URL(url, 'http://test').searchParams
      for (const key of ['page', 'page_size', 'hr_page', 'row_order', 'tab']) expect(query.has(key)).toBe(false)
    }
    await waitFor(() => expect(revokeUrl).toHaveBeenCalledTimes(2))
  })
})
