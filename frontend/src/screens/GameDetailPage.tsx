import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { ApiClientError, isCanonicalUuid, useGame } from '@/api'
import { DataFreshness } from '@/components/DataFreshness'
import { GameScore, GameTeams } from '@/components/GameSummaryView'
import { formatGameStart } from '@/components/gamePresentation'
import { MetricValueView } from '@/components/MetricValueView'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from '@/components/PageStates'
import { UrlStateBoundary } from '@/routing/UrlStateBoundary'
import { parseUrlState } from '@/routing/urlState'

type EventFilter = 'ALL' | 'HOME' | 'AWAY'

function safeReturnTarget(state: unknown) {
  if (!state || typeof state !== 'object' || !('from' in state)) return '/games'
  const from = (state as { from?: unknown }).from
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/games'
}

export function GameDetailPage() {
  const { gameId = '' } = useParams()
  const location = useLocation()
  const queryState = parseUrlState(new URLSearchParams(location.search), 'gameDetail')
  if (queryState.issues.length) return <UrlStateBoundary route="gameDetail"><span /></UrlStateBoundary>
  if (!isCanonicalUuid(gameId)) {
    return <ErrorState error={new ApiClientError({
      kind: 'api',
      status: 404,
      code: 'NOT_FOUND',
      message: 'Canonical game ID is invalid.',
    })} />
  }
  return <GameDetailContent gameId={gameId} />
}

function GameDetailContent({ gameId }: { gameId: string }) {
  const query = useGame(gameId)
  const location = useLocation()
  const navigate = useNavigate()
  const [eventFilter, setEventFilter] = useState<EventFilter>('ALL')
  const backTarget = safeReturnTarget(location.state)
  const hashValue = location.hash.startsWith('#hr-') ? location.hash.slice(4) : null
  const focusedEvent = hashValue && isCanonicalUuid(hashValue)
    ? query.data?.home_runs.find((item) => item.id === hashValue)
    : undefined
  const focusNotice = !location.hash ? 'NONE' : focusedEvent ? 'FOCUSED' : 'MISSING'

  useEffect(() => {
    if (!focusedEvent) return
    requestAnimationFrame(() => {
      const node = document.getElementById(`hr-${focusedEvent.id}`)
      node?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
      node?.focus()
    })
  }, [focusedEvent])

  const events = useMemo(() => {
    if (!query.data || eventFilter === 'ALL') return query.data?.home_runs ?? []
    const id = eventFilter === 'HOME' ? query.data.game.home_team.id : query.data.game.away_team.id
    return query.data.home_runs.filter((event) => event.batting_team.id === id)
  }, [eventFilter, query.data])

  if (query.isPending) return <InitialLoading label="Loading game detail" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (!query.data) return null
  const { game } = query.data
  const clearHash = () => navigate(`${location.pathname}${location.search}`, { replace: true, state: location.state })

  return (
    <div className="space-y-8">
      <Link className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4" to={backTarget}>← Back</Link>
      {query.isFetching ? <RefreshingStatus /> : null}
      <header className="rounded-2xl bg-primary p-6 text-primary-foreground md:p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm text-primary-foreground/75">{game.official_date ?? 'Official date unknown'} · {game.status.replaceAll('_', ' ')}</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight"><GameTeams game={game} linked={false} /></h1>
            <p className="mt-2 text-sm text-primary-foreground/75">{formatGameStart(game)}{game.venue?.name ? ` · ${game.venue.name}` : ''}</p>
          </div>
          <div className="flex items-end gap-8">
            <div><p className="text-xs text-primary-foreground/70">Score</p><p className="mt-1 text-2xl"><GameScore game={game} /></p></div>
            <div><p className="text-xs text-primary-foreground/70">Home runs</p><p className="mt-1 text-2xl"><MetricValueView label="Game home runs" metric={game.hr_count} /></p></div>
          </div>
        </div>
      </header>

      {focusNotice === 'MISSING' ? (
        <section aria-live="polite" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <span>Requested home-run event is not available in this game.</span>
          <button className="rounded-md border border-amber-700 px-3 py-2 font-medium" onClick={clearHash} type="button">Clear event focus</button>
        </section>
      ) : null}

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <div className="space-y-8">
          <section aria-labelledby="hr-events">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div><h2 className="text-xl font-semibold" id="hr-events">Home-run events</h2><p className="mt-1 text-sm text-muted-foreground">Verified events are listed independently from the authoritative total above.</p></div>
              <label className="text-sm font-medium">Display events
                <select className="ml-2 min-h-11 rounded-md border bg-background px-3" onChange={(event) => setEventFilter(event.target.value as EventFilter)} value={eventFilter}>
                  <option value="ALL">All teams</option>
                  <option value="HOME">Home team</option>
                  <option value="AWAY">Away team</option>
                </select>
              </label>
            </div>
            {events.length ? <ol className="mt-4 space-y-3">{events.map((event) => {
              const focused = hashValue === event.id && focusNotice === 'FOCUSED'
              return (
                <li
                  aria-label={`Home run by ${event.batter.display_name ?? 'unknown batter'}`}
                  className={`rounded-xl border bg-card p-4 outline-none ${focused ? 'ring-2 ring-primary ring-offset-2' : ''}`}
                  id={`hr-${event.id}`}
                  key={event.id}
                  tabIndex={-1}
                >
                  {focused ? <p className="mb-2 text-xs font-semibold uppercase tracking-wide">Requested event</p> : null}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><Link className="font-semibold underline-offset-4 hover:underline" to={`/players/${event.batter.id}`}>{event.batter.display_name ?? 'Unknown batter'}</Link><p className="text-sm text-muted-foreground">{event.batting_team.display_name ?? event.batting_team.abbreviation ?? 'Unknown team'}</p></div>
                    <p className="text-sm font-medium">{event.inning ? `${event.half_inning} ${event.inning}` : 'Inning unknown'}</p>
                  </div>
                  <p className="mt-3 text-sm">Pitcher: {event.pitcher ? <Link className="underline underline-offset-4" to={`/players/${event.pitcher.id}`}>{event.pitcher.display_name ?? 'Unknown pitcher'}</Link> : <span className="text-muted-foreground">Unknown</span>}</p>
                  {event.provenance ? <p className="mt-2 text-xs text-muted-foreground">Source: {event.provenance.source_label}</p> : null}
                </li>
              )
            })}</ol> : <div className="mt-4"><EmptyState>No verified home-run events match this display filter.</EmptyState></div>}
          </section>

          <section aria-labelledby="participants">
            <h2 className="text-xl font-semibold" id="participants">Evidenced participants</h2>
            <p className="mt-1 text-sm text-muted-foreground">Only positive appearance evidence returned by the API is shown.</p>
            {query.data.participants.length ? (
              <div className="mt-4 overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><caption className="sr-only">Positively evidenced game participants</caption><thead className="bg-muted/60"><tr><th className="px-4 py-3" scope="col">Player</th><th className="px-4 py-3" scope="col">Team</th><th className="px-4 py-3" scope="col">Roles</th><th className="px-4 py-3" scope="col">PA</th></tr></thead><tbody>{query.data.participants.map((participant) => <tr className="border-t" key={`${participant.player.id}:${participant.team.id}`}><td className="px-4 py-3"><Link className="font-medium underline-offset-4 hover:underline" to={`/players/${participant.player.id}`}>{participant.player.display_name ?? 'Unknown player'}</Link></td><td className="px-4 py-3">{participant.team.display_name ?? participant.team.abbreviation ?? 'Unknown team'}</td><td className="px-4 py-3">{participant.roles.join(', ') || 'Role unavailable'}</td><td className="px-4 py-3"><MetricValueView label="Plate appearances" metric={participant.pa_count} /></td></tr>)}</tbody></table></div>
            ) : <div className="mt-4"><EmptyState>No positively evidenced participants are available.</EmptyState></div>}
          </section>
        </div>

        <aside aria-labelledby="coverage" className="space-y-4">
          <div><h2 className="text-xl font-semibold" id="coverage">Evidence coverage</h2><p className="mt-1 text-sm text-muted-foreground">Current state by independent evidence domain.</p></div>
          <ul className="divide-y rounded-xl border bg-card">{query.data.coverage.map((coverage) => <li className="p-4" key={coverage.domain}><div className="flex items-center justify-between gap-3"><span className="text-sm font-medium">{coverage.domain.replaceAll('_', ' ')}</span><span className="text-sm">{coverage.state === 'COMPLETE' ? 'Complete' : coverage.state === 'PARTIAL' ? 'Partial' : coverage.state === 'UNAVAILABLE' ? 'Unavailable' : 'Unknown'}</span></div>{coverage.reason_codes.length ? <p className="mt-2 text-xs text-muted-foreground">{coverage.reason_codes.join(', ').replaceAll('_', ' ')}</p> : null}</li>)}</ul>
          {query.data.coverage.some((item) => item.state !== 'COMPLETE') ? <PartialDataNotice>Some game evidence is not complete. Known facts remain visible.</PartialDataNotice> : null}
        </aside>
      </div>
      <DataFreshness meta={query.data.meta} />
    </div>
  )
}
