import { useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import {
  HOME_AWAY,
  WINDOWS,
  shareDatasetRevision,
  useGames,
  usePlayerLeaderboard,
  usePlayers,
  useSeasons,
  useTeamDetail,
  useTeamHomeRuns,
  type TeamDetailParams,
} from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { GameScore, GameTeams } from '@/components/GameSummaryView'
import { MetricValueView } from '@/components/MetricValueView'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { PlayerLeaderboardTable } from '@/components/PlayerLeaderboardTable'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState, type UrlState, type UrlStateKey } from '@/routing/urlState'

const tabs = [
  ['overview', 'Overview'], ['players', 'Players'], ['games', 'Games'], ['hr-log', 'HR Log'],
] as const

export function TeamDetailPage() {
  const { teamId = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'teamDetail')
  const seasons = useSeasons({ page_size: 100 })
  useEffect(() => {
    if (!parsed.issues.length && !parsed.state.season && seasons.data?.results[0]) {
      setSearchParams(updateUrlState(searchParams, { season: String(seasons.data.results[0].year) }), { replace: true })
    }
  }, [parsed.issues.length, parsed.state.season, searchParams, seasons.data, setSearchParams])
  if (parsed.issues.length) return <UrlStateBoundary route="teamDetail"><span /></UrlStateBoundary>
  if (!parsed.state.season) {
    if (seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
    return <InitialLoading label="Loading team scope" />
  }
  return <TeamDetailContent seasons={seasons.data?.results ?? []} seasonsError={seasons.error} seasonsPending={seasons.isPending} teamId={teamId} />
}

function TeamDetailContent({ teamId, seasons, seasonsError, seasonsPending }: { teamId: string; seasons: NonNullable<ReturnType<typeof useSeasons>['data']>['results']; seasonsError: unknown; seasonsPending: boolean }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const state = parseUrlState(searchParams, 'teamDetail').state
  const season = Number(state.season)
  const detailParams: TeamDetailParams = { season, window: state.window as TeamDetailParams['window'], home_away: state.home_away as TeamDetailParams['home_away'], cutoff: state.cutoff }
  const detail = useTeamDetail(teamId, detailParams)
  const activeTab = state.tab ?? 'overview'
  const change = (key: UrlStateKey, value: string | null) => {
    const analytical = new Set<UrlStateKey>(['window', 'home_away', 'cutoff'])
    const pages = key === 'season'
      ? { discovery_page: '1', comparison_page: '1', games_page: '1', hr_page: '1' }
      : analytical.has(key) ? { comparison_page: '1', hr_page: '1' } : {}
    setSearchParams(updateUrlState(searchParams, { [key]: value, ...pages }))
  }
  return (
    <div className="space-y-7">
      <header><Link className="text-sm underline underline-offset-4" to={`/teams${state.season ? `?season=${state.season}` : ''}`}>← Teams</Link><h1 className="mt-2 text-3xl font-semibold tracking-tight">{detail.data?.team.display_name ?? 'Team detail'}</h1>{detail.data ? <p className="mt-1 text-sm text-muted-foreground">{detail.data.team.abbreviation ?? 'Abbreviation unavailable'} · {[detail.data.team.league, detail.data.team.division].filter(Boolean).join(' · ') || 'League/division unavailable'}</p> : null}</header>
      <section aria-label="Team analytical filters" className="grid gap-3 rounded-xl border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><label className="text-sm font-medium" htmlFor="team-season">Season</label><select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" id="team-season" onChange={(event) => change('season', event.target.value)} value={state.season}><option disabled value="">{seasonsPending ? 'Loading seasons…' : 'Choose season'}</option>{seasons.map((item) => <option key={item.id} value={item.year}>{item.label ?? item.year}</option>)}</select>{seasonsError ? <span className="text-xs text-destructive">Season options unavailable.</span> : null}</div>
        <label className="text-sm font-medium">Window<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('window', event.target.value)} value={state.window ?? 'SEASON'}>{WINDOWS.map((window) => <option key={window} value={window}>{window === 'SEASON' ? 'Season' : window}</option>)}</select></label>
        <label className="text-sm font-medium">Home / away<select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('home_away', event.target.value)} value={state.home_away ?? 'ALL'}>{HOME_AWAY.map((value) => <option key={value} value={value}>{value === 'ALL' ? 'All' : value === 'HOME' ? 'Home' : 'Away'}</option>)}</select></label>
        <label className="text-sm font-medium">Cutoff date<input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => change('cutoff', event.target.value || null)} type="date" value={state.cutoff ?? ''} /></label>
      </section>
      {detail.isPending ? <InitialLoading label="Loading team detail" /> : null}
      {detail.error ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {detail.data ? <>
        {detail.isFetching ? <RefreshingStatus /> : null}
        <nav aria-label="Team detail sections" className="flex gap-2 overflow-x-auto border-b pb-2">{tabs.map(([key, label]) => <button aria-current={activeTab === key ? 'page' : undefined} className={`min-h-11 whitespace-nowrap rounded-md px-4 text-sm font-medium ${activeTab === key ? 'bg-primary text-primary-foreground' : 'border'}`} key={key} onClick={() => change('tab', key)} type="button">{label}</button>)}</nav>
        {activeTab === 'overview' ? <Overview detail={detail.data} /> : null}
        {activeTab === 'players' ? <PlayersPanel season={season} state={state} teamId={teamId} /> : null}
        {activeTab === 'games' ? <GamesPanel season={season} state={state} teamId={teamId} /> : null}
        {activeTab === 'hr-log' ? <HomeRunsPanel season={season} state={state} teamId={teamId} /> : null}
      </> : null}
    </div>
  )
}

function Overview({ detail }: { detail: NonNullable<ReturnType<typeof useTeamDetail>['data']> }) {
  const metrics = [
    ['team.hr', 'Home runs'], ['team.pa', 'Plate appearances'], ['team.hr_per_pa', 'HR / PA'], ['team.pa_per_hr', 'PA / HR'],
    ['team.hr_per_game', 'HR / team game'], ['team.hr_game_pct', 'Games with HR %'], ['team.multi_hr_games', 'Multi-HR games'],
    ['team.avg_hr_gap_games', 'Average HR gap'], ['team.median_hr_gap_games', 'Median HR gap'],
    ['team.current_hr_drought_games', 'Current HR drought'], ['team.max_hr_drought_games', 'Maximum HR drought'],
    ['team.current_hr_streak_games', 'Current HR streak'], ['team.max_hr_streak_games', 'Maximum HR streak'],
  ] as const
  const partial = Object.values(detail.metrics).some((metric) => metric.state !== 'VALUE')
  const gameCount = detail.scope.actual_game_count
  return <section aria-labelledby="team-overview-title" className="space-y-4"><h2 className="text-xl font-semibold" id="team-overview-title">Overview</h2>{partial ? <PartialDataNotice>Unavailable metrics remain explicitly labeled.</PartialDataNotice> : null}<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([id, label]) => <article className="rounded-xl border p-4" key={id}><h3 className="text-sm font-medium text-muted-foreground">{label}</h3><div className="mt-2 text-lg font-semibold"><MetricValueView label={label} metric={detail.metrics[id]} /></div></article>)}</div><p className="text-sm text-muted-foreground">{gameCount === null ? `${detail.scope.known_eligible_game_count} known eligible team games; membership is ${detail.scope.selection_state.toLowerCase().replaceAll('_', ' ')}.` : `${gameCount} team ${gameCount === 1 ? 'game' : 'games'} available`} · cutoff {detail.scope.cutoff_date ?? 'unresolved'} · {detail.scope.home_away.toLowerCase()}</p><p aria-disabled="true" className="text-sm text-muted-foreground">Recurrence matrix — UI coming in B19</p><CoverageList coverage={detail.coverage} /><DataFreshness meta={detail.meta} /></section>
}

function CoverageList({ coverage }: { coverage: NonNullable<ReturnType<typeof useTeamDetail>['data']>['coverage'] }) {
  return <section aria-labelledby="team-coverage-title"><h3 className="font-semibold" id="team-coverage-title">Coverage</h3>{coverage.length ? <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-2">{coverage.map((item) => <li className="rounded-md border px-3 py-2" key={item.domain}>{item.domain.replaceAll('_', ' ')}: {item.state.replaceAll('_', ' ')}</li>)}</ul> : <p className="mt-1 text-sm text-muted-foreground">No selected-game coverage rows.</p>}</section>
}

function PlayersPanel({ teamId, season, state }: { teamId: string; season: number; state: UrlState }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const discoveryPage = Number(state.discovery_page ?? 1)
  const comparisonPage = Number(state.comparison_page ?? 1)
  const pageSize = state.page_size ? Number(state.page_size) : undefined
  const identities = usePlayers({ season, team: teamId, page: discoveryPage, page_size: pageSize })
  const comparison = usePlayerLeaderboard({ season, team: teamId, window: state.window as '7G' | '15G' | '30G' | '60G' | 'SEASON' | undefined, home_away: state.home_away as 'ALL' | 'HOME' | 'AWAY' | undefined, cutoff: state.cutoff, page: comparisonPage, page_size: pageSize })
  const mismatch = identities.data && comparison.data && !shareDatasetRevision(identities.data, comparison.data)
  return <section aria-labelledby="team-players-title" className="space-y-5"><header><h2 className="text-xl font-semibold" id="team-players-title">Players</h2><p className="text-sm text-muted-foreground">Source-supported team association and participation evidence; this is not a complete historical roster.</p></header>{mismatch ? <PartialDataNotice>The identity and comparison sections use different dataset revisions and are not merged.</PartialDataNotice> : null}<Panel title="Associated identities" query={identities}>{identities.data?.results.length ? <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/60"><tr><th className="px-4 py-3" scope="col">Player</th><th className="px-4 py-3" scope="col">Position</th><th className="px-4 py-3" scope="col">Bats</th></tr></thead><tbody>{identities.data.results.map((player) => <tr className="border-t" key={player.id}><th className="px-4 py-3" scope="row"><Link className="underline underline-offset-4" to={`/players/${player.id}`}>{player.display_name ?? 'Unknown player'}</Link></th><td className="px-4 py-3">{player.primary_position ?? 'Unknown'}</td><td className="px-4 py-3">{player.bats}</td></tr>)}</tbody></table></div> : identities.data ? <EmptyState>No source-supported player associations for this season.</EmptyState> : null}<Pager count={identities.data?.count} label="Team player discovery" next={Boolean(identities.data?.next)} page={discoveryPage} previous={Boolean(identities.data?.previous)} setPage={(page) => setSearchParams(updateUrlState(searchParams, { discovery_page: String(page) }))} />{identities.data ? <DataFreshness meta={identities.data.meta} /> : null}</Panel><Panel title="Analytical comparison" query={comparison}>{comparison.data?.results.length ? <PlayerLeaderboardTable compact ordering="-hr" rows={comparison.data.results} /> : comparison.data ? <EmptyState>No analytical player rows for this scope.</EmptyState> : null}<Pager count={comparison.data?.count} label="Team player comparison" next={Boolean(comparison.data?.next)} page={comparisonPage} previous={Boolean(comparison.data?.previous)} setPage={(page) => setSearchParams(updateUrlState(searchParams, { comparison_page: String(page) }))} />{comparison.data ? <DataFreshness meta={comparison.data.meta} /> : null}</Panel></section>
}

function GamesPanel({ teamId, season, state }: { teamId: string; season: number; state: UrlState }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Number(state.games_page ?? 1)
  const games = useGames({ season, team: teamId, page, page_size: state.page_size ? Number(state.page_size) : undefined })
  return <section aria-labelledby="team-games-title" className="space-y-4"><h2 className="text-xl font-semibold" id="team-games-title">Games</h2><p className="text-sm text-muted-foreground">Season schedule records for this team. Analytical window filters do not change this list.</p><Panel query={games}>{games.data?.results.length ? <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/60"><tr><th className="px-4 py-3" scope="col">Date</th><th className="px-4 py-3" scope="col">Teams</th><th className="px-4 py-3" scope="col">Status</th><th className="px-4 py-3" scope="col">Score</th><th className="px-4 py-3" scope="col">HR</th></tr></thead><tbody>{games.data.results.map((game) => <tr className="border-t" key={game.id}><td className="px-4 py-3"><Link className="underline underline-offset-4" to={`/games/${game.id}`}>{game.official_date ?? 'Unknown date'}</Link></td><td className="px-4 py-3"><GameTeams game={game} /></td><td className="px-4 py-3">{game.status.replaceAll('_', ' ')}</td><td className="px-4 py-3"><GameScore game={game} /></td><td className="px-4 py-3"><MetricValueView label="Game home runs" metric={game.hr_count} /></td></tr>)}</tbody></table></div> : games.data ? <EmptyState>No team games were found.</EmptyState> : null}<Pager count={games.data?.count} label="Team games" next={Boolean(games.data?.next)} page={page} previous={Boolean(games.data?.previous)} setPage={(next) => setSearchParams(updateUrlState(searchParams, { games_page: String(next) }))} />{games.data ? <DataFreshness meta={games.data.meta} /> : null}</Panel></section>
}

function HomeRunsPanel({ teamId, season, state }: { teamId: string; season: number; state: UrlState }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Number(state.hr_page ?? 1)
  const ordering = (state.hr_ordering ?? 'official_date') as 'official_date' | '-official_date'
  const homeRuns = useTeamHomeRuns(teamId, { season, window: state.window as '7G' | '15G' | '30G' | '60G' | 'SEASON' | undefined, home_away: state.home_away as 'ALL' | 'HOME' | 'AWAY' | undefined, cutoff: state.cutoff, ordering, page, page_size: state.page_size ? Number(state.page_size) : undefined })
  return <section aria-labelledby="team-hr-title" className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><h2 className="text-xl font-semibold" id="team-hr-title">HR Log</h2><label className="text-sm font-medium">Event order<select aria-label="Event order" className="ml-2 min-h-11 rounded-md border bg-background px-3" onChange={(event) => setSearchParams(updateUrlState(searchParams, { hr_ordering: event.target.value, hr_page: '1' }))} value={ordering}><option value="official_date">Oldest first</option><option value="-official_date">Newest first</option></select></label></div>{homeRuns.data ? <div className="rounded-xl border p-4"><p className="text-sm text-muted-foreground">Authoritative home-run total</p><div className="mt-1 text-xl font-semibold"><MetricValueView label="Team home-run total" metric={homeRuns.data.total_hr} /></div><p className="mt-1 text-xs text-muted-foreground">{homeRuns.data.count} verified event records are listed across pages. This record count is not the analytical total.</p></div> : null}<Panel query={homeRuns}>{homeRuns.data?.results.length ? <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/60"><tr><th className="px-4 py-3" scope="col">Date</th><th className="px-4 py-3" scope="col">Batter</th><th className="px-4 py-3" scope="col">Pitcher</th><th className="px-4 py-3" scope="col">Game</th></tr></thead><tbody>{homeRuns.data.results.map((event) => <tr className="border-t" key={event.id}><td className="px-4 py-3">{event.official_date ?? 'Unknown date'}</td><td className="px-4 py-3"><Link className="underline underline-offset-4" to={`/players/${event.batter.id}`}>{event.batter.display_name ?? 'Unknown batter'}</Link></td><td className="px-4 py-3">{event.pitcher?.display_name ?? 'Unknown pitcher'}</td><td className="px-4 py-3"><Link className="underline underline-offset-4" to={`/games/${event.game_id}#hr-${event.id}`}>Open game</Link>{event.provenance ? <span className="ml-2 text-xs text-muted-foreground">{event.provenance.source_label}</span> : null}</td></tr>)}</tbody></table></div> : homeRuns.data ? <EmptyState>No verified team home-run events are listed for this scope.</EmptyState> : null}<Pager count={homeRuns.data?.count} label="Team home runs" next={Boolean(homeRuns.data?.next)} page={page} previous={Boolean(homeRuns.data?.previous)} setPage={(next) => setSearchParams(updateUrlState(searchParams, { hr_page: String(next) }))} />{homeRuns.data ? <DataFreshness meta={homeRuns.data.meta} /> : null}</Panel></section>
}

function Panel({ title, query, children }: { title?: string; query: { isPending: boolean; isFetching: boolean; error: unknown; data: unknown; refetch: () => unknown }; children: React.ReactNode }) {
  return <section className="space-y-3">{title ? <h3 className="font-semibold">{title}</h3> : null}{query.isPending ? <InitialLoading label={`Loading ${title?.toLowerCase() ?? 'panel'}`} /> : null}{query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}{query.data ? <>{query.isFetching ? <RefreshingStatus /> : null}{children}</> : null}</section>
}

function Pager({ count, label, page, previous, next, setPage }: { count?: number; label: string; page: number; previous: boolean; next: boolean; setPage: (page: number) => void }) {
  if (count === undefined) return null
  return <nav aria-label={`${label} pagination`} className="flex items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{count} listed records</p><div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!previous} onClick={() => setPage(page - 1)} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!next} onClick={() => setPage(page + 1)} type="button">Next</button></div></nav>
}
