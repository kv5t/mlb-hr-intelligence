import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import {
  HOME_AWAY,
  WINDOWS,
  useSeasons,
  useTeamRecurrence,
  type MatrixCell,
  type MatrixColumn,
  type MatrixPlayerRow,
  type TeamRecurrenceParams,
  type TeamRecurrenceResponse,
} from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { MetricValueView } from '@/components/MetricValueView'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlStateKey } from '@/routing/urlState'

export type MatrixRowOrder = 'season_hr_desc' | 'window_hr_desc' | 'name'

function metricNumber(metric: MatrixPlayerRow['player_season_hr']) {
  return metric.state === 'VALUE' ? metric.value : null
}

function orderMatrixRows(rows: MatrixPlayerRow[], order: MatrixRowOrder): MatrixPlayerRow[] {
  return [...rows].sort((left, right) => {
    if (order === 'name') {
      const byName = (left.player.display_name ?? '').localeCompare(right.player.display_name ?? '')
      return byName || left.player.id.localeCompare(right.player.id)
    }
    const leftValue = metricNumber(order === 'season_hr_desc' ? left.player_season_hr : left.window_hr)
    const rightValue = metricNumber(order === 'season_hr_desc' ? right.player_season_hr : right.window_hr)
    if (leftValue === null && rightValue !== null) return 1
    if (leftValue !== null && rightValue === null) return -1
    if (leftValue !== null && rightValue !== null && leftValue !== rightValue) return rightValue - leftValue
    return left.player.id.localeCompare(right.player.id)
  })
}

export function TeamRecurrencePage() {
  const { teamId = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'teamRecurrence')
  const seasons = useSeasons({ page_size: 100 })

  useEffect(() => {
    if (parsed.issues.length) return
    const changes: Partial<Record<UrlStateKey, string>> = {}
    if (!parsed.state.window) changes.window = '30G'
    if (!parsed.state.season && seasons.data?.results[0]) changes.season = String(seasons.data.results[0].year)
    if (Object.keys(changes).length) setSearchParams(updateUrlState(searchParams, changes), { replace: true })
  }, [parsed.issues.length, parsed.state.season, parsed.state.window, searchParams, seasons.data, setSearchParams])

  if (parsed.issues.length) return <UrlStateBoundary route="teamRecurrence"><span /></UrlStateBoundary>
  if (!parsed.state.season || !parsed.state.window) {
    if (!parsed.state.season && seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
    return <InitialLoading label="Loading recurrence scope" />
  }
  return <TeamRecurrenceContent seasons={seasons.data?.results ?? []} seasonsError={seasons.error} teamId={teamId} />
}

function TeamRecurrenceContent({ teamId, seasons, seasonsError }: {
  teamId: string
  seasons: NonNullable<ReturnType<typeof useSeasons>['data']>['results']
  seasonsError: unknown
}) {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const state = parseUrlState(searchParams, 'teamRecurrence').state
  const params: TeamRecurrenceParams = {
    season: Number(state.season),
    window: state.window as TeamRecurrenceParams['window'],
    home_away: state.home_away as TeamRecurrenceParams['home_away'],
    cutoff: state.cutoff,
  }
  const query = useTeamRecurrence(teamId, params)
  const rowOrder = (state.row_order ?? 'season_hr_desc') as MatrixRowOrder
  const from = `${location.pathname}${location.search}`
  const change = (key: UrlStateKey, value: string | null) => setSearchParams(updateUrlState(searchParams, { [key]: value }))

  if (query.isPending) return <InitialLoading label="Loading team recurrence matrix" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (!query.data) return null
  const response = query.data
  const rows = orderMatrixRows(response.rows, rowOrder)
  const partial = response.scope.selection_state !== 'VALUE' || response.coverage.some((item) => item.state !== 'COMPLETE') || response.rows.some((row) => row.cells.some((cell) => cell.state === 'UNKNOWN' || cell.state === 'INCOMPLETE'))

  return (
    <div className="space-y-6">
      <header>
        <Link className="text-sm underline underline-offset-4" to={`/teams/${teamId}?${teamDetailQuery(response)}`}>← Team detail</Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{response.team.display_name ?? 'Team'} recurrence</h1>
        <p className="mt-1 text-sm text-muted-foreground">Player evidence across the selected team-game window.</p>
      </header>
      <MatrixFilters change={change} rowOrder={rowOrder} seasons={seasons} seasonsError={seasonsError} state={state} />
      {query.isFetching ? <RefreshingStatus /> : null}
      <ScopeSummary response={response} />
      {partial ? <PartialDataNotice>Unknown and partial evidence remains labeled and is never treated as zero.</PartialDataNotice> : null}
      {response.scope.selection_state !== 'VALUE' ? <UnresolvedMatrix response={response} /> : response.columns.length === 0 ? <EmptyState>No final regular team games are available in this resolved scope.</EmptyState> : (
        <>
          <MatrixLegend />
          <TeamMatrix teamName={response.team.display_name ?? 'Unknown team'} columns={response.columns} from={from} rows={rows} />
          <MobileMatrix teamName={response.team.display_name ?? 'Unknown team'} columns={response.columns} from={from} rows={rows} />
        </>
      )}
      <Coverage coverage={response.coverage} />
      <DataFreshness meta={response.meta} />
    </div>
  )
}

function teamDetailQuery(response: TeamRecurrenceResponse) {
  const query = new URLSearchParams({ season: String(response.scope.season), window: response.scope.window, home_away: response.scope.home_away })
  if (response.scope.cutoff_source === 'EXPLICIT' && response.scope.cutoff_date) query.set('cutoff', response.scope.cutoff_date)
  query.sort()
  return query.toString()
}

function MatrixFilters({ change, rowOrder, seasons, seasonsError, state }: {
  change: (key: UrlStateKey, value: string | null) => void
  rowOrder: MatrixRowOrder
  seasons: NonNullable<ReturnType<typeof useSeasons>['data']>['results']
  seasonsError: unknown
  state: ReturnType<typeof parseUrlState>['state']
}) {
  return <section aria-label="Team recurrence filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 xl:grid-cols-5">
    <div><label className="text-sm font-medium" htmlFor="matrix-season">Season</label><select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" id="matrix-season" onChange={(event) => change('season', event.target.value)} value={state.season}>{seasons.map((season) => <option key={season.id} value={season.year}>{season.label ?? season.year}</option>)}</select>{seasonsError ? <span className="text-xs text-destructive">Season options unavailable.</span> : null}</div>
    <label className="text-sm font-medium">Window<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('window', event.target.value)} value={state.window}>{WINDOWS.map((window) => <option key={window} value={window}>{window === 'SEASON' ? 'Season' : window}</option>)}</select></label>
    <label className="text-sm font-medium">Home / away<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('home_away', event.target.value)} value={state.home_away ?? 'ALL'}>{HOME_AWAY.map((value) => <option key={value} value={value}>{value[0] + value.slice(1).toLowerCase()}</option>)}</select></label>
    <label className="text-sm font-medium">Cutoff date<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('cutoff', event.target.value || null)} type="date" value={state.cutoff ?? ''} /></label>
    <label className="text-sm font-medium">Row order<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('row_order', event.target.value)} value={rowOrder}><option value="season_hr_desc">Season HR</option><option value="window_hr_desc">Window HR</option><option value="name">Player name</option></select></label>
  </section>
}

function ScopeSummary({ response }: { response: TeamRecurrenceResponse }) {
  const metrics = [
    ['team.hr', 'Team HR'], ['team.hr_game_pct', 'Games with HR %'],
    ['team.median_hr_gap_games', 'Median HR gap'], ['team.current_hr_drought_games', 'Current drought'],
  ] as const
  return <section aria-labelledby="matrix-scope-title" className="space-y-3"><h2 className="text-xl font-semibold" id="matrix-scope-title">Scope summary</h2><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([id, label]) => <article className="rounded-xl border p-3" key={id}><h3 className="text-xs font-medium text-muted-foreground">{label}</h3><div className="mt-1 font-semibold"><MetricValueView label={label} metric={response.metrics[id]} /></div></article>)}</div><p className="text-sm text-muted-foreground">{response.scope.actual_game_count === null ? `${response.scope.known_eligible_game_count} known eligible games; membership ${response.scope.selection_state.toLowerCase().replaceAll('_', ' ')}.` : `${response.scope.actual_game_count} team games available`} · {response.scope.window} · {response.scope.home_away.toLowerCase()} · cutoff {response.scope.cutoff_date ?? 'unresolved'}</p></section>
}

function UnresolvedMatrix({ response }: { response: TeamRecurrenceResponse }) {
  return <section aria-labelledby="unresolved-matrix-title" className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-950"><h2 className="font-semibold" id="unresolved-matrix-title">Matrix membership is not definitive</h2><p className="mt-2 text-sm">Selection state: {response.scope.selection_state.replaceAll('_', ' ')}. At least {response.scope.known_eligible_game_count} eligible games are known for {response.scope.window} through {response.scope.cutoff_date ?? 'an unresolved cutoff'}. No matrix was fabricated.</p></section>
}

function MatrixLegend() {
  return <section aria-labelledby="matrix-legend-title" className="rounded-xl border p-4"><h2 className="font-semibold" id="matrix-legend-title">Cell legend</h2><ul className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-sm"><li><strong>1+</strong> HR count</li><li><strong>0</strong> verified zero</li><li><strong>DNP</strong> did not appear</li><li><strong>0 PA</strong> appeared without a PA</li><li><strong>Not with team</strong></li><li><strong>?</strong> unavailable or unknown evidence</li><li><strong>Partial</strong> known incomplete evidence</li></ul></section>
}

function cellText(cell: MatrixCell) {
  switch (cell.state) {
    case 'HR_COUNT': return String(cell.hr_count)
    case 'KNOWN_ZERO': return '0'
    case 'DNP': return 'DNP'
    case 'ZERO_PA_APPEARANCE': return '0 PA'
    case 'NOT_WITH_TEAM': return 'Not with team'
    case 'UNKNOWN': return '?'
    case 'INCOMPLETE': return 'Partial'
  }
}

function cellDescription(teamName: string, player: MatrixPlayerRow, column: MatrixColumn, cell: MatrixCell) {
  const playerName = player.player.display_name ?? 'Unknown player'
  const opponent = column.opponent.display_name ?? 'unknown opponent'
  const gameNumber = column.scheduled_game_number ? `, game ${column.scheduled_game_number}` : ''
  const context = `${playerName}, representing ${teamName}, ${column.official_date}${gameNumber}, vs ${opponent}, ${column.home_away.toLowerCase()}`
  switch (cell.state) {
    case 'HR_COUNT': return `${context}, ${cell.hr_count} home run${cell.hr_count === 1 ? '' : 's'}`
    case 'KNOWN_ZERO': return `${context}, verified zero home runs`
    case 'DNP': return `${context}, did not appear`
    case 'ZERO_PA_APPEARANCE': return `${context}, appeared with zero plate appearances`
    case 'NOT_WITH_TEAM': return `${context}, not with team`
    case 'UNKNOWN': return `${context}, participation unknown`
    case 'INCOMPLETE': return `${context}, partial evidence`
  }
}

function TeamMatrix({ teamName, columns, from, rows }: { teamName: string; columns: MatrixColumn[]; from: string; rows: MatrixPlayerRow[] }) {
  const [focus, setFocus] = useState({ row: 0, column: 0 })
  const [open, setOpen] = useState<string | null>(null)
  const root = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const start = window.__matrixPayloadAvailableAt ?? performance.now()
    let second = 0
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => {
        if (root.current) {
          root.current.dataset.matrixReady = 'true'
          root.current.dataset.renderMs = (performance.now() - start).toFixed(2)
          const measuredPerformance = performance as Performance & { memory?: { usedJSHeapSize: number } }
          root.current.dataset.browser = navigator.userAgent
          root.current.dataset.payloadBytes = String(window.__matrixPayloadBytes ?? '')
          root.current.dataset.heapGrowthBytes = measuredPerformance.memory && window.__matrixHeapBaseline
            ? String(measuredPerformance.memory.usedJSHeapSize - window.__matrixHeapBaseline)
            : ''
          root.current.dataset.longestTaskMs = String(window.__matrixLongestTask ?? '')
          root.current.dataset.interactionLongestTaskMs = String(window.__matrixInteractionLongestTask ?? '')
        }
      })
    })
    return () => {
      cancelAnimationFrame(first)
      cancelAnimationFrame(second)
    }
  }, [columns, rows])
  const focusCell = (row: number, column: number) => {
    const next = { row: Math.max(0, Math.min(rows.length - 1, row)), column: Math.max(0, Math.min(columns.length - 1, column)) }
    setFocus(next)
    requestAnimationFrame(() => root.current?.querySelector<HTMLElement>(`[data-matrix-row="${next.row}"][data-matrix-column="${next.column}"]`)?.focus())
  }
  return <div className="hidden overflow-x-auto rounded-xl border md:block" ref={root}><table className="min-w-max border-collapse text-center text-xs"><caption className="sr-only">Team home-run recurrence matrix. Use arrow keys to move between game cells.</caption><thead className="bg-muted/80"><tr><th className="sticky left-0 z-30 min-w-48 bg-muted px-3 py-3 text-left" scope="col">Player</th><th className="sticky left-48 z-30 min-w-24 bg-muted px-3 py-3" scope="col">Season HR</th><th className="sticky left-72 z-30 min-w-24 border-r bg-muted px-3 py-3" scope="col">Window HR</th>{columns.map((column) => <th className="min-w-28 px-2 py-3" key={column.game_id} scope="col"><Link className="underline underline-offset-4" state={{ from }} to={`/games/${column.game_id}`}><span className="block">{column.official_date}</span>{column.scheduled_game_number ? <span className="block">Game {column.scheduled_game_number}</span> : null}<span className="block font-normal">{column.home_away === 'HOME' ? 'vs' : '@'} {column.opponent.abbreviation ?? column.opponent.display_name ?? 'Opponent'}</span></Link></th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr className="border-t" key={row.player.id}><th className="sticky left-0 z-20 bg-background px-3 py-2 text-left" scope="row"><Link className="font-medium underline underline-offset-4" to={`/players/${row.player.id}`}>{row.player.display_name ?? 'Unknown player'}</Link></th><td className="sticky left-48 z-20 bg-background px-3 py-2"><MetricValueView label={`${row.player.display_name ?? 'Player'} season HR`} metric={row.player_season_hr} /></td><td className="sticky left-72 z-20 border-r bg-background px-3 py-2"><MetricValueView label={`${row.player.display_name ?? 'Player'} window HR`} metric={row.window_hr} /></td>{row.cells.map((cell, columnIndex) => {
    const key = `${row.player.id}:${columns[columnIndex].game_id}`
    const actionable = cell.state === 'HR_COUNT'
    return <td aria-label={cellDescription(teamName, row, columns[columnIndex], cell)} className="relative border-l px-2 py-2 outline-offset-[-3px] focus-visible:outline-2 focus-visible:outline-ring" data-matrix-column={columnIndex} data-matrix-row={rowIndex} key={key} onClick={() => actionable && setOpen(open === key ? null : key)} onKeyDown={(event) => {
      if (event.key === 'Escape' && open === key) { event.preventDefault(); setOpen(null); event.currentTarget.focus(); return }
      if (event.target !== event.currentTarget) return
      const moves: Record<string, [number, number]> = { ArrowLeft: [rowIndex, columnIndex - 1], ArrowRight: [rowIndex, columnIndex + 1], ArrowUp: [rowIndex - 1, columnIndex], ArrowDown: [rowIndex + 1, columnIndex], Home: [rowIndex, 0], End: [rowIndex, columns.length - 1] }
      if (moves[event.key]) { event.preventDefault(); focusCell(...moves[event.key]); return }
      if (actionable && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); setOpen(key); requestAnimationFrame(() => root.current?.querySelector<HTMLElement>(`[data-detail-for="${key}"] a`)?.focus()) }
    }} tabIndex={focus.row === rowIndex && focus.column === columnIndex ? 0 : -1}><span aria-hidden="true" className={cell.state === 'HR_COUNT' ? 'font-bold' : 'text-muted-foreground'}>{cellText(cell)}</span>{open === key && actionable ? <div className="absolute left-1/2 z-40 mt-2 min-w-24 -translate-x-1/2 rounded-md border bg-background p-2 shadow-lg" data-detail-for={key}>{cell.home_run_event_ids.map((eventId, index) => <Link className="block min-h-8 whitespace-nowrap underline" key={eventId} state={{ from }} to={`/games/${columns[columnIndex].game_id}#hr-${eventId}`}>HR {index + 1}</Link>)}</div> : null}</td>
  })}</tr>)}</tbody></table></div>
}

function MobileMatrix({ teamName, columns, from, rows }: { teamName: string; columns: MatrixColumn[]; from: string; rows: MatrixPlayerRow[] }) {
  const [playerId, setPlayerId] = useState(rows[0]?.player.id ?? '')
  const row = rows.find((item) => item.player.id === playerId) ?? rows[0]
  if (!row) return null
  return <section aria-labelledby="mobile-matrix-title" className="space-y-4 md:hidden"><h2 className="font-semibold" id="mobile-matrix-title">Player game sequence</h2><label className="text-sm font-medium">Player<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => setPlayerId(event.target.value)} value={row.player.id}>{rows.map((item) => <option key={item.player.id} value={item.player.id}>{item.player.display_name ?? 'Unknown player'}</option>)}</select></label><div className="grid grid-cols-2 gap-3"><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Season HR</p><MetricValueView label="Season HR" metric={row.player_season_hr} /></div><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Window HR</p><MetricValueView label="Window HR" metric={row.window_hr} /></div></div><ol className="space-y-2">{columns.map((column, index) => { const cell = row.cells[index]; return <li className="rounded-lg border p-3" key={column.game_id}><div className="flex items-start justify-between gap-3"><div><Link className="font-medium underline underline-offset-4" state={{ from }} to={`/games/${column.game_id}`}>{column.official_date}{column.scheduled_game_number ? ` · Game ${column.scheduled_game_number}` : ''}</Link><p className="text-xs text-muted-foreground">{column.home_away === 'HOME' ? 'vs' : '@'} {column.opponent.display_name ?? 'Opponent'} · {column.home_away.toLowerCase()}</p></div><span aria-label={cellDescription(teamName, row, column, cell)} className="font-semibold">{cellText(cell)}</span></div>{cell.state === 'HR_COUNT' ? <div className="mt-2 flex flex-wrap gap-3">{cell.home_run_event_ids.map((eventId, eventIndex) => <Link className="text-sm underline" key={eventId} state={{ from }} to={`/games/${column.game_id}#hr-${eventId}`}>HR {eventIndex + 1}</Link>)}</div> : null}</li> })}</ol></section>
}

function Coverage({ coverage }: { coverage: TeamRecurrenceResponse['coverage'] }) {
  return <section aria-labelledby="matrix-coverage-title"><h2 className="font-semibold" id="matrix-coverage-title">Coverage</h2>{coverage.length ? <ul className="mt-2 flex flex-wrap gap-2 text-sm">{coverage.map((item) => <li className="rounded-md border px-3 py-2" key={item.domain}>{item.domain.replaceAll('_', ' ')}: {item.state.replaceAll('_', ' ')}</li>)}</ul> : <p className="mt-1 text-sm text-muted-foreground">No selected-game coverage rows.</p>}</section>
}
