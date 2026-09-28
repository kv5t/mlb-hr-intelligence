import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { shareDatasetRevision, usePlayerLeaderboard, usePlayers, useSeasons, useTeams } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { PlayerAnalyticsFilters } from '@/components/PlayerAnalyticsFilters'
import { PlayerLeaderboardTable } from '@/components/PlayerLeaderboardTable'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlStateKey } from '@/routing/urlState'
import { discoveryParams, leaderboardParams } from '@/screens/playerScreenState'

export function PlayersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'players')
  const seasons = useSeasons({ page_size: 100 })
  useEffect(() => {
    if (!parsed.issues.length && !parsed.state.season && seasons.data?.results[0]) {
      setSearchParams(updateUrlState(searchParams, { season: String(seasons.data.results[0].year) }), { replace: true })
    }
  }, [parsed.issues.length, parsed.state.season, searchParams, seasons.data, setSearchParams])
  if (parsed.issues.length) return <UrlStateBoundary route="players"><span /></UrlStateBoundary>
  if (!parsed.state.season) {
    if (seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
    return <InitialLoading label="Loading player scope" />
  }
  return <PlayersContent season={Number(parsed.state.season)} seasons={seasons.data?.results ?? []} seasonsError={seasons.error} seasonsPending={seasons.isPending} retrySeasons={() => void seasons.refetch()} />
}

function PlayersContent({ season, seasons, seasonsError, seasonsPending, retrySeasons }: { season: number; seasons: NonNullable<ReturnType<typeof useSeasons>['data']>['results']; seasonsError: unknown; seasonsPending: boolean; retrySeasons: () => void }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'players')
  const comparisonParams = leaderboardParams(parsed.state, season)
  const identities = usePlayers(discoveryParams(parsed.state, season))
  const comparison = usePlayerLeaderboard(comparisonParams)
  const teams = useTeams({ season, page_size: 100 })
  const change = (key: UrlStateKey, value: string | null) => {
    const shared = new Set<UrlStateKey>(['season', 'team', 'search', 'position', 'bats'])
    setSearchParams(updateUrlState(searchParams, {
      [key]: value,
      comparison_page: '1',
      ...(shared.has(key) ? { discovery_page: '1' } : {}),
    }))
  }
  const effectiveOrdering = comparisonParams.ordering ?? '-hr'
  const sort = (field: Parameters<React.ComponentProps<typeof PlayerLeaderboardTable>['onSort']>[0]) => change('ordering', effectiveOrdering === `-${field}` ? field : `-${field}`)
  const discoveryPage = Number(parsed.state.discovery_page ?? 1)
  const comparisonPage = Number(parsed.state.comparison_page ?? 1)
  const mismatch = identities.data && comparison.data && !shareDatasetRevision(identities.data, comparison.data)
  const partial = comparison.data?.results.some((row) => Object.values(row.metrics).some((metric) => metric.state !== 'VALUE'))
  return (
    <div className="space-y-8">
      <header><h1 className="text-3xl font-semibold tracking-tight">Players</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Discover canonical player identities and compare separately scoped analytics.</p></header>
      <PlayerAnalyticsFilters change={change} retrySeasons={retrySeasons} retryTeams={() => void teams.refetch()} seasons={seasons} seasonsError={seasonsError} seasonsPending={seasonsPending} state={parsed.state} teams={teams.data?.results ?? []} teamsError={teams.error} teamsPending={teams.isPending} />
      {mismatch ? <PartialDataNotice>Discovery and comparison were published at different revisions. The sections remain separate and are not merged.</PartialDataNotice> : null}
      <section aria-labelledby="player-discovery-title" className="space-y-4">
        <header><h2 className="text-xl font-semibold" id="player-discovery-title">Player discovery</h2><p className="text-sm text-muted-foreground">Identity and source-supported association only. No rolling metrics are attached.</p></header>
        {identities.isPending ? <InitialLoading label="Loading player identities" /> : null}
        {identities.error ? <ErrorState error={identities.error} onRetry={() => void identities.refetch()} /> : null}
        {identities.data ? <>{identities.isFetching ? <RefreshingStatus /> : null}{identities.data.results.length ? <div className="overflow-x-auto rounded-xl border"><table aria-label="Player identity discovery" className="w-full text-left text-sm"><thead className="bg-muted/60"><tr><th className="px-4 py-3" scope="col">Player</th><th className="px-4 py-3" scope="col">Position</th><th className="px-4 py-3" scope="col">Bats</th><th className="px-4 py-3" scope="col">Throws</th><th className="px-4 py-3" scope="col">Represented team</th></tr></thead><tbody>{identities.data.results.map((player) => <tr className="border-t" key={player.id}><th className="px-4 py-3 font-medium" scope="row"><Link className="underline underline-offset-4" to={`/players/${player.id}`}>{player.display_name ?? 'Unknown player'}</Link></th><td className="px-4 py-3">{player.primary_position ?? 'Unknown'}</td><td className="px-4 py-3">{player.bats}</td><td className="px-4 py-3">{player.throws}</td><td className="px-4 py-3">{player.represented_team?.abbreviation ?? player.represented_team?.display_name ?? '—'}</td></tr>)}</tbody></table></div> : <EmptyState>No player identities match these filters.</EmptyState>}<nav aria-label="Player discovery pagination" className="mt-3 flex items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{identities.data.count} identities</p><div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!identities.data.previous} onClick={() => setSearchParams(updateUrlState(searchParams, { discovery_page: String(discoveryPage - 1) }))} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!identities.data.next} onClick={() => setSearchParams(updateUrlState(searchParams, { discovery_page: String(discoveryPage + 1) }))} type="button">Next</button></div></nav><DataFreshness meta={identities.data.meta} /></> : null}
      </section>
      <section aria-labelledby="player-comparison-title" className="space-y-4">
        <header><h2 className="text-xl font-semibold" id="player-comparison-title">Analytical comparison</h2><p className="text-sm text-muted-foreground">Metrics use each player’s own batting-game window and denominator.</p></header>
        {comparison.isPending ? <InitialLoading label="Loading player comparison" /> : null}
        {comparison.error ? <ErrorState error={comparison.error} onRetry={() => void comparison.refetch()} /> : null}
        {comparison.data ? <>{comparison.isFetching ? <RefreshingStatus /> : null}{partial ? <PartialDataNotice>Partial and unavailable metric rows remain visible.</PartialDataNotice> : null}{comparison.data.results.length ? <PlayerLeaderboardTable compact onSort={sort} ordering={effectiveOrdering} rows={comparison.data.results} /> : <EmptyState>No analytical player rows match this scope.</EmptyState>}<nav aria-label="Player comparison pagination" className="mt-3 flex items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{comparison.data.count} comparison records</p><div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!comparison.data.previous} onClick={() => setSearchParams(updateUrlState(searchParams, { comparison_page: String(comparisonPage - 1) }))} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50" disabled={!comparison.data.next} onClick={() => setSearchParams(updateUrlState(searchParams, { comparison_page: String(comparisonPage + 1) }))} type="button">Next</button></div></nav><DataFreshness meta={comparison.data.meta} /></> : null}
      </section>
    </div>
  )
}
