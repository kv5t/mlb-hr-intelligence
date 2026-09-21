import { useEffect } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { WINDOWS, useSeasons, useToday, type TodayParams } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { GameSummaryCard } from '@/components/GameSummaryView'
import { MetricValueView } from '@/components/MetricValueView'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState, updateUrlState } from '@/routing/urlState'

function localDate() {
  const now = new Date()
  const part = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${part(now.getMonth() + 1)}-${part(now.getDate())}`
}

export function TodayPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const parsed = parseUrlState(searchParams, 'today')
  const seasons = useSeasons({ page_size: 100 })

  useEffect(() => {
    if (parsed.issues.length || seasons.data?.results.length === 0) return
    const changes: Record<string, string> = {}
    if (!parsed.state.season && seasons.data) changes.season = String(seasons.data.results[0].year)
    if (!parsed.state.date) changes.date = localDate()
    if (Object.keys(changes).length) {
      setSearchParams(updateUrlState(searchParams, changes), { replace: true })
    }
  }, [parsed.issues.length, parsed.state.date, parsed.state.season, searchParams, seasons.data, setSearchParams])

  if (parsed.issues.length) return <UrlStateBoundary route="today"><span /></UrlStateBoundary>
  if (seasons.isPending) return <InitialLoading label="Loading Today filters" />
  if (seasons.error) return <ErrorState error={seasons.error} onRetry={() => void seasons.refetch()} />
  if (!seasons.data?.results.length) return <EmptyState>No seasons are available.</EmptyState>
  if (!parsed.state.season || !parsed.state.date) return <InitialLoading label="Preparing explicit Today scope" />

  const params: TodayParams = {
    season: Number(parsed.state.season),
    date: parsed.state.date,
    window: (parsed.state.window ?? 'SEASON') as TodayParams['window'],
  }
  return <TodayContent params={params} seasons={seasons.data.results} />
}

function TodayContent({ params, seasons }: { params: TodayParams; seasons: Array<{ year: number; label: string | null }> }) {
  const query = useToday(params)
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const setFilter = (key: 'season' | 'date' | 'window', value: string) => {
    setSearchParams(updateUrlState(searchParams, { [key]: value }), { replace: false })
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-5 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Today</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Games and recent descriptive home-run form for an explicit calendar date.</p>
        </div>
        <div aria-label="Today filters" className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm font-medium">Season
            <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => setFilter('season', event.target.value)} value={params.season}>
              {seasons.map((season) => <option key={season.year} value={season.year}>{season.label ?? season.year}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Date
            <input className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => setFilter('date', event.target.value)} type="date" value={params.date} />
          </label>
          <label className="text-sm font-medium">Leader window
            <select className="mt-1 min-h-11 w-full rounded-md border bg-background px-3" onChange={(event) => setFilter('window', event.target.value)} value={params.window ?? 'SEASON'}>
              {WINDOWS.map((window) => <option key={window} value={window}>{window === 'SEASON' ? 'Season' : window}</option>)}
            </select>
          </label>
        </div>
      </header>

      {query.isPending ? <InitialLoading label="Loading games and leaders" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <>
          {query.isFetching ? <RefreshingStatus /> : null}
          <section aria-labelledby="today-games">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold" id="today-games">Games</h2>
                <p className="mt-1 text-sm text-muted-foreground">Schedule rows remain visible when HR evidence is incomplete.</p>
              </div>
              <Link className="text-sm font-medium underline underline-offset-4" to={`/games?season=${params.season}&date_from=${params.date}&date_to=${params.date}`}>View in Games</Link>
            </div>
            {query.data.games.length ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {query.data.games.map((game) => <GameSummaryCard from={`${location.pathname}${location.search}`} game={game} key={game.id} />)}
              </div>
            ) : <div className="mt-4"><EmptyState>No games are scheduled for this date.</EmptyState></div>}
          </section>

          <section aria-labelledby="recent-leaders">
            <h2 className="text-xl font-semibold" id="recent-leaders">Recent HR leaders</h2>
            <p className="mt-1 text-sm text-muted-foreground">Server-ranked observed players for the selected window.</p>
            {query.data.recent_leaders_availability.state === 'UNKNOWN' ? <div className="mt-4"><PartialDataNotice>Observed leaders are shown, but ranking completeness is unknown.</PartialDataNotice></div> : null}
            {query.data.recent_leaders_availability.state === 'INCOMPLETE' ? <div className="mt-4"><PartialDataNotice>Observed leaders are shown from a partially verified population.</PartialDataNotice></div> : null}
            {query.data.recent_leaders_availability.state === 'NOT_APPLICABLE' ? <div className="mt-4"><EmptyState>No eligible final games are available for leader analysis.</EmptyState></div> : null}
            {query.data.recent_leaders.length ? (
              <div className="mt-4 flex snap-x gap-4 overflow-x-auto pb-3 lg:grid lg:grid-cols-5 lg:overflow-visible">
                {query.data.recent_leaders.map((leader, index) => {
                  const metrics = leader.metrics
                  return (
                    <article className="min-w-64 snap-start rounded-xl border bg-card p-4 lg:min-w-0" key={leader.player.id}>
                      <p className="text-xs font-medium text-muted-foreground">Observed rank {index + 1}</p>
                      <Link className="mt-1 block font-semibold underline-offset-4 hover:underline" to={`/players/${leader.player.id}`}>{leader.player.display_name ?? 'Unknown player'}</Link>
                      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                        {[
                          ['player.hr', 'HR'],
                          ['player.hr_game_pct', 'Games with HR %'],
                          ['player.current_hr_drought_games', 'Drought'],
                          ['player.current_hr_streak_games', 'Streak'],
                        ].map(([id, label]) => metrics[id] ? (
                          <div key={id}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 font-medium"><MetricValueView label={label} metric={metrics[id]} /></dd></div>
                        ) : null)}
                      </dl>
                    </article>
                  )
                })}
              </div>
            ) : null}
          </section>
          <DataFreshness meta={query.data.meta} />
        </>
      ) : null}
    </div>
  )
}
