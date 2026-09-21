import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { GAME_STATUSES, useGames, useSeasons, useTeams, type GameSummary, type GamesParams } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { GameScore, GameSummaryCard, GameTeams } from '@/components/GameSummaryView'
import { formatGameStart } from '@/components/gamePresentation'
import { MetricValueView } from '@/components/MetricValueView'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlStateKey } from '@/routing/urlState'

export function GamesPage() {
  const [searchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'games')
  if (parsed.issues.length) return <UrlStateBoundary route="games"><span /></UrlStateBoundary>
  const params: GamesParams = {
    season: parsed.state.season ? Number(parsed.state.season) : undefined,
    date_from: parsed.state.date_from,
    date_to: parsed.state.date_to,
    team: parsed.state.team,
    status: parsed.state.status as GamesParams['status'],
    ordering: parsed.state.ordering as GamesParams['ordering'],
    page: parsed.state.page ? Number(parsed.state.page) : undefined,
    page_size: parsed.state.page_size ? Number(parsed.state.page_size) : undefined,
  }
  return <GamesContent params={params} />
}

const features = tableFeatures({})
const column = createColumnHelper<typeof features, GameSummary>()

function GamesContent({ params }: { params: GamesParams }) {
  const games = useGames(params)
  const seasons = useSeasons({ page_size: 100 })
  const teams = useTeams({ season: params.season, page_size: 100 })
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const from = `${location.pathname}${location.search}`

  const change = (key: UrlStateKey, value: string | null, resetPage = true) => {
    setSearchParams(updateUrlState(searchParams, { [key]: value }, { resetPage }))
  }
  const changeOrdering = (field: 'official_date' | 'scheduled_start_at_utc') => {
    const next = params.ordering === field ? `-${field}` : field
    change('ordering', next)
  }
  const sortIcon = (field: string) => params.ordering === field
    ? <ArrowUp aria-hidden className="size-4" />
    : params.ordering === `-${field}`
      ? <ArrowDown aria-hidden className="size-4" />
      : <ArrowUpDown aria-hidden className="size-4" />

  const columns = column.columns([
    column.accessor('official_date', {
      header: () => <button className="inline-flex items-center gap-1" onClick={() => changeOrdering('official_date')} type="button">Date {sortIcon('official_date')}</button>,
      cell: (info) => info.getValue() ?? 'Unknown date',
    }),
    column.display({ header: 'Teams', cell: ({ row }) => <GameTeams game={row.original} /> }),
    column.accessor('scheduled_start_at_utc', {
      header: () => <button className="inline-flex items-center gap-1" onClick={() => changeOrdering('scheduled_start_at_utc')} type="button">Start / status {sortIcon('scheduled_start_at_utc')}</button>,
      cell: ({ row }) => <><span className="block">{formatGameStart(row.original)}</span><span className="text-xs text-muted-foreground">{row.original.status.replaceAll('_', ' ')}</span></>,
    }),
    column.display({ header: 'Score', cell: ({ row }) => <GameScore game={row.original} /> }),
    column.accessor('hr_count', { header: 'HR count', cell: (info) => <MetricValueView label="Game home runs" metric={info.getValue()} /> }),
    column.display({ id: 'open', header: 'Game', cell: ({ row }) => <Link className="font-medium underline underline-offset-4" state={{ from }} to={`/games/${row.original.id}`}>Open</Link> }),
  ])
  const table = useTable({ data: games.data?.results ?? [], columns, features })
  const currentPage = params.page ?? 1
  const size = params.page_size ?? 25
  const pageCount = games.data ? Math.max(1, Math.ceil(games.data.count / size)) : 1
  const partial = games.data?.results.some((game) => game.hr_count.state === 'UNKNOWN' || game.hr_count.state === 'INCOMPLETE')

  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Games</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Browse schedule and completed games without hiding incomplete evidence.</p>
      </header>

      <section aria-label="Game filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-sm font-medium">Season
          <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('season', event.target.value || null)} value={params.season ?? ''}>
            <option value="">All seasons</option>
            {seasons.data?.results.map((season) => <option key={season.id} value={season.year}>{season.label ?? season.year}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">From
          <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('date_from', event.target.value || null)} type="date" value={params.date_from ?? ''} />
        </label>
        <label className="text-sm font-medium">To
          <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('date_to', event.target.value || null)} type="date" value={params.date_to ?? ''} />
        </label>
        <label className="text-sm font-medium">Team
          <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('team', event.target.value || null)} value={params.team ?? ''}>
            <option value="">All teams</option>
            {teams.data?.results.map((team) => <option key={team.id} value={team.id}>{team.display_name ?? team.abbreviation ?? 'Unknown team'}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">Status
          <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('status', event.target.value || null)} value={params.status ?? ''}>
            <option value="">All statuses</option>
            {GAME_STATUSES.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
      </section>

      {games.isPending ? <InitialLoading label="Loading games" /> : null}
      {games.error ? <ErrorState error={games.error} onRetry={() => void games.refetch()} /> : null}
      {games.data ? (
        <>
          {games.isFetching ? <RefreshingStatus /> : null}
          {partial ? <PartialDataNotice>Schedule rows are available; some home-run totals are unknown or partial.</PartialDataNotice> : null}
          {games.data.results.length ? (
            <>
              <div className="hidden overflow-x-auto rounded-xl border md:block">
                <table className="w-full border-collapse text-left text-sm">
                  <caption className="sr-only">Games matching the current server-side filters</caption>
                  <thead className="bg-muted/60">
                    {table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th className="whitespace-nowrap px-4 py-3 font-medium" key={header.id} scope="col">{header.isPlaceholder ? null : <table.FlexRender header={header} />}</th>)}</tr>)}
                  </thead>
                  <tbody>{table.getRowModel().rows.map((row) => <tr className="border-t" key={row.id}>{row.getAllCells().map((cell) => <td className="px-4 py-3 align-top" key={cell.id}><table.FlexRender cell={cell} /></td>)}</tr>)}</tbody>
                </table>
              </div>
              <div className="grid gap-4 md:hidden">{games.data.results.map((game) => <GameSummaryCard from={from} game={game} key={game.id} />)}</div>
            </>
          ) : <EmptyState>No games match these filters.</EmptyState>}
          <nav aria-label="Games pagination" className="flex flex-wrap items-center justify-between gap-4 border-t pt-4">
            <p className="text-sm text-muted-foreground">Page {currentPage} of {pageCount} · {games.data.count} listed games</p>
            <div className="flex gap-2">
              <button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50" disabled={!games.data.previous} onClick={() => change('page', String(currentPage - 1), false)} type="button">Previous</button>
              <button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50" disabled={!games.data.next} onClick={() => change('page', String(currentPage + 1), false)} type="button">Next</button>
            </div>
          </nav>
          <DataFreshness meta={games.data.meta} />
        </>
      ) : null}
    </div>
  )
}
