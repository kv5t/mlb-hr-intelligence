import { useEffect, type ReactNode } from 'react'
import { Link, NavLink, useParams, useSearchParams } from 'react-router-dom'

import { ApiClientError, HOME_AWAY, WINDOWS, isCanonicalUuid, useSeasons, useTeams, type PlayerSummary, type PlayerDetailResponse } from '@/api'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { DataFreshness } from '@/components/DataFreshness'
import { MetricValueView } from '@/components/MetricValueView'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlState, type UrlStateKey } from '@/routing/urlState'
import { playerScopeSearch } from './playerAnalyticalState'

type PlayerRoute = 'playerDetail' | 'playerRecurrence' | 'playerHomeRuns'

export function PlayerScopeBoundary({ route, children }: { route: PlayerRoute; children: ReactNode }) {
  const { playerId = '' } = useParams()
  const [search, setSearch] = useSearchParams()
  const parsed = parseUrlState(search, route)
  const seasons = useSeasons({ page_size: 100 })
  useEffect(() => {
    if (parsed.issues.length || !isCanonicalUuid(playerId)) return
    const changes: Partial<Record<UrlStateKey, string>> = {}
    if (!parsed.state.window) changes.window = route === 'playerDetail' ? 'SEASON' : '30G'
    if (!parsed.state.season && seasons.data?.results[0]) changes.season = String(seasons.data.results[0].year)
    if (Object.keys(changes).length) setSearch(updateUrlState(search, changes), { replace: true })
  }, [parsed.issues.length, parsed.state.season, parsed.state.window, playerId, route, search, seasons.data, setSearch])
  if (!isCanonicalUuid(playerId)) return <ErrorState error={new ApiClientError({ kind: 'api', status: 404, code: 'NOT_FOUND', message: 'Player not found.' })} />
  if (parsed.issues.length) return <UrlStateBoundary route={route}><span /></UrlStateBoundary>
  if (!parsed.state.season || !parsed.state.window) {
    if (!parsed.state.season && seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
    if (!parsed.state.season && seasons.data && !seasons.data.results.length) return <EmptyState>No seasons are available.</EmptyState>
    return <InitialLoading label="Loading player scope" />
  }
  return children
}

export function PlayerHeader({ player, state, title }: { player: PlayerSummary; state: UrlState; title: string }) {
  const query = playerScopeSearch(state)
  return <header className="space-y-3"><h1 className="text-3xl font-semibold tracking-tight">{player.display_name ?? 'Player'} · {title}</h1><p className="text-sm text-muted-foreground">Position: {player.primary_position ?? 'Unknown'} · Bats: {player.bats} · Throws: {player.throws}</p>{player.represented_team ? <p className="text-sm">Evidenced represented team: <Link className="underline" to={`/teams/${player.represented_team.id}?season=${state.season}`}>{player.represented_team.display_name ?? 'Unknown team'}</Link></p> : null}<nav aria-label="Player sections" className="flex flex-wrap gap-2">{[['', 'Overview'], ['/recurrence', 'Recurrence'], ['/home-runs', 'Home Runs']].map(([suffix, label]) => <NavLink className={({ isActive }) => `inline-flex min-h-11 items-center rounded-md border px-4 text-sm ${isActive ? 'font-bold underline' : ''}`} end key={suffix} to={`/players/${player.id}${suffix}?${query}`}>{label}</NavLink>)}</nav></header>
}

export function PlayerFilters({ state }: { state: UrlState }) {
  const [search, setSearch] = useSearchParams()
  const seasons = useSeasons({ page_size: 100 })
  const teams = useTeams({ season: Number(state.season), page_size: 100 })
  const change = (key: UrlStateKey, value: string) => setSearch(updateUrlState(search, { [key]: value || null, ...(search.has('hr_page') ? { hr_page: '1' } : {}) }))
  return <section aria-label="Player analytical filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 xl:grid-cols-5">
    <label className="text-sm font-medium">Season<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('season', event.target.value)} value={state.season}>{!seasons.data?.results.some((season) => String(season.year) === state.season) ? <option value={state.season}>{state.season}</option> : null}{seasons.data?.results.map((season) => <option key={season.id} value={season.year}>{season.label ?? season.year}</option>)}</select>{seasons.isPending ? <span>Loading season options…</span> : null}{seasons.error ? <span>Season options unavailable. <button className="underline" onClick={() => void seasons.refetch()} type="button">Retry season options</button></span> : null}</label>
    <label className="text-sm font-medium">Window<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('window', event.target.value)} value={state.window}>{WINDOWS.map((window) => <option key={window} value={window}>{window === 'SEASON' ? 'Season' : window}</option>)}</select></label>
    <label className="text-sm font-medium">Team scope<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('team', event.target.value)} value={state.team ?? ''}><option value="">All represented teams</option>{state.team && !teams.data?.results.some((team) => team.id === state.team) ? <option value={state.team}>Selected team: {state.team}</option> : null}{teams.data?.results.map((team) => <option key={team.id} value={team.id}>{team.display_name ?? team.id}</option>)}</select>{teams.isPending ? <span>Loading team options…</span> : null}{teams.error ? <span>Team options unavailable. <button className="underline" onClick={() => void teams.refetch()} type="button">Retry team options</button></span> : null}</label>
    <label className="text-sm font-medium">Home / away<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('home_away', event.target.value)} value={state.home_away ?? 'ALL'}>{HOME_AWAY.map((value) => <option key={value} value={value}>{value[0] + value.slice(1).toLowerCase()}</option>)}</select></label>
    <label className="text-sm font-medium">Cutoff date<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('cutoff', event.target.value)} type="date" value={state.cutoff ?? ''} /></label>
  </section>
}

export function PlayerScopeSummary({ scope }: { scope: PlayerDetailResponse['scope'] }) {
  return <div className="space-y-2 text-sm"><p>{scope.actual_game_count === null ? `${scope.known_eligible_game_count} known eligible batting games; membership ${scope.selection_state.replaceAll('_', ' ').toLowerCase()}.` : `${scope.actual_game_count} batting games available`} · {scope.window} · cutoff {scope.cutoff_date ?? 'unresolved'} · {scope.home_away.toLowerCase()}</p>{scope.team_filter_id ? <p className="text-muted-foreground">Requested team scope: {scope.team_filter_id}. This filter alone does not establish team representation.</p> : null}<p className="text-muted-foreground">Current drought and streak scan through the cutoff and may exceed the displayed window. Maximum runs and gap summaries use only this window.</p></div>
}

export function PlayerEvidence({ coverage, meta }: Pick<PlayerDetailResponse, 'coverage' | 'meta'>) {
  return <><section aria-labelledby="player-coverage-title"><h2 className="font-semibold" id="player-coverage-title">Coverage</h2>{coverage.length ? <ul className="mt-2 flex flex-wrap gap-2 text-sm">{coverage.map((item) => <li className="rounded-md border px-3 py-2" key={item.domain}>{item.domain.replaceAll('_', ' ')}: {item.state.replaceAll('_', ' ')}</li>)}</ul> : <p className="text-sm text-muted-foreground">No selected-game coverage rows.</p>}</section><DataFreshness meta={meta} /></>
}

export function PlayerMetricGroup({ title, metrics, items }: { title: string; metrics: PlayerDetailResponse['metrics']; items: readonly (readonly [string, string])[] }) {
  return <section className="space-y-3"><h2 className="text-xl font-semibold">{title}</h2><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{items.map(([id, label]) => <article className="rounded-xl border p-4" key={id}><h3 className="text-sm text-muted-foreground">{label}</h3><div className="mt-2 text-lg font-semibold"><MetricValueView label={label} metric={metrics[id]} /></div></article>)}</div></section>
}

export function PlayerQueryState({ query, children }: { query: { isPending: boolean; isFetching: boolean; error: unknown; data: unknown; refetch: () => unknown }; children: ReactNode }) {
  if (query.isPending) return <InitialLoading label="Loading player analytics" />
  if (!query.data && query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <>{query.isFetching ? <RefreshingStatus /> : null}{query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}{children}</>
}

export function PlayerUnresolved({ scope }: { scope: PlayerDetailResponse['scope'] }) {
  return <PartialDataNotice>Batting-game membership is unresolved: {scope.selection_state.replaceAll('_', ' ')}. {scope.known_eligible_game_count} known eligible games in {scope.window} through {scope.cutoff_date ?? 'an unresolved cutoff'}. No sequence or selected records are fabricated.</PartialDataNotice>
}
