import { ExportActions } from '@/components/ExportActions'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

import { usePlayerLeaderboard, useSeasons, useTeams } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { PlayerAnalyticsFilters } from '@/components/PlayerAnalyticsFilters'
import { PlayerLeaderboardTable } from '@/components/PlayerLeaderboardTable'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlStateKey } from '@/routing/urlState'
import { leaderboardParams } from '@/screens/playerScreenState'

export function LeaguePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'league')
  const seasons = useSeasons({ page_size: 100 })
  useEffect(() => {
    if (!parsed.issues.length && !parsed.state.season && seasons.data?.results[0]) {
      setSearchParams(updateUrlState(searchParams, { season: String(seasons.data.results[0].year) }), { replace: true })
    }
  }, [parsed.issues.length, parsed.state.season, searchParams, seasons.data, setSearchParams])
  if (parsed.issues.length) return <UrlStateBoundary route="league"><span /></UrlStateBoundary>
  if (!parsed.state.season) {
    if (seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
    return <InitialLoading label="Loading league scope" />
  }
  return <LeagueContent season={Number(parsed.state.season)} seasons={seasons.data?.results ?? []} seasonsError={seasons.error} seasonsPending={seasons.isPending} retrySeasons={() => void seasons.refetch()} />
}

function LeagueContent({ season, seasons, seasonsError, seasonsPending, retrySeasons }: { season: number; seasons: NonNullable<ReturnType<typeof useSeasons>['data']>['results']; seasonsError: unknown; seasonsPending: boolean; retrySeasons: () => void }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'league')
  const params = leaderboardParams(parsed.state, season)
  const leaderboard = usePlayerLeaderboard(params)
  const teams = useTeams({ season, page_size: 100 })
  const change = (key: UrlStateKey, value: string | null, resetPage = true) => setSearchParams(updateUrlState(searchParams, { [key]: value }, { resetPage }))
  const effectiveOrdering = params.ordering ?? '-hr'
  const sort = (field: Parameters<NonNullable<React.ComponentProps<typeof PlayerLeaderboardTable>['onSort']>>[0]) => {
    const next = effectiveOrdering === `-${field}` ? field : `-${field}`
    change('ordering', next)
  }
  const page = params.page ?? 1
  const partial = leaderboard.data?.results.some((row) => Object.values(row.metrics).some((metric) => metric.state !== 'VALUE'))
  return (
    <div className="space-y-7">
      <header><h1 className="text-3xl font-semibold tracking-tight">League</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Compare player production and recurrence using each player’s verified batting-game sample.</p></header>
      <PlayerAnalyticsFilters change={change} retrySeasons={retrySeasons} retryTeams={() => void teams.refetch()} seasons={seasons} seasonsError={seasonsError} seasonsPending={seasonsPending} state={parsed.state} teams={teams.data?.results ?? []} teamsError={teams.error} teamsPending={teams.isPending} />
      {leaderboard.isPending ? <InitialLoading label="Loading player leaderboard" /> : null}
      {leaderboard.error ? <ErrorState error={leaderboard.error} onRetry={() => void leaderboard.refetch()} /> : null}
      {leaderboard.data ? <>
        <ExportActions target={{ kind: 'leaderboard', params }} />
        {leaderboard.isFetching ? <RefreshingStatus /> : null}
        {partial ? <PartialDataNotice>Players remain visible when one or more metrics are unavailable or partial.</PartialDataNotice> : null}
        {leaderboard.data.results.length ? <PlayerLeaderboardTable onSort={sort} ordering={effectiveOrdering} rows={leaderboard.data.results} /> : <EmptyState>No players match this analytical scope.</EmptyState>}
        <nav aria-label="League leaderboard pagination" className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">{leaderboard.data.count} player records</p>
          <div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!leaderboard.data.previous} onClick={() => change('page', String(page - 1), false)} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!leaderboard.data.next} onClick={() => change('page', String(page + 1), false)} type="button">Next</button></div>
        </nav>
        <DataFreshness meta={leaderboard.data.meta} />
      </> : null}
    </div>
  )
}
