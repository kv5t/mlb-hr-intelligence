import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { usePlayerHomeRuns } from '@/api'
import { EmptyState } from '@/components/PageStates'
import { MetricValueView } from '@/components/MetricValueView'
import { parseUrlState, updateUrlState } from '@/routing/urlState'
import { playerAnalyticalParams } from './playerAnalyticalState'
import { PlayerScopeBoundary, PlayerHeader, PlayerFilters, PlayerScopeSummary, PlayerEvidence, PlayerQueryState, PlayerUnresolved } from './PlayerAnalyticalLayout'

export function PlayerHomeRunsPage() {
  return <PlayerScopeBoundary route="playerHomeRuns"><PlayerHomeRunsContent /></PlayerScopeBoundary>
}
function PlayerHomeRunsContent() {
  const { playerId = '' } = useParams()
  const location = useLocation()
  const [search, setSearch] = useSearchParams()
  const state = parseUrlState(search, 'playerHomeRuns').state
  const page = Number(state.hr_page ?? 1)
  const ordering = (state.hr_ordering ?? 'official_date') as 'official_date' | '-official_date'
  const query = usePlayerHomeRuns(playerId, { ...playerAnalyticalParams(state), ordering, page, page_size: state.page_size ? Number(state.page_size) : undefined })
  const response = query.data
  const from = `${location.pathname}${location.search}`
  return <PlayerQueryState query={query}>{response ? <div className="space-y-6"><PlayerHeader player={response.player} state={state} title="Home Runs" /><PlayerFilters state={state} /><PlayerScopeSummary scope={response.scope} /><section className="rounded-xl border p-4" aria-labelledby="player-total-title"><h2 className="text-sm text-muted-foreground" id="player-total-title">Authoritative home-run total</h2><div className="mt-2 text-xl font-semibold"><MetricValueView label="Player home-run total" metric={response.total_hr} /></div><p className="mt-2 text-sm">{response.count} verified event records across pages. This record count is not the analytical total.</p></section><label className="block text-sm font-medium">Event order<select className="ml-3 min-h-11 rounded-md border bg-background px-3" onChange={(event) => setSearch(updateUrlState(search, { hr_ordering: event.target.value, hr_page: '1' }))} value={ordering}><option value="official_date">Oldest first</option><option value="-official_date">Newest first</option></select></label>{response.scope.selection_state !== 'VALUE' ? <PlayerUnresolved scope={response.scope} /> : response.results.length ? <section aria-labelledby="player-events-title"><h2 className="text-xl font-semibold" id="player-events-title">Verified home-run events</h2><ol className="mt-3 space-y-3">{response.results.map((event) => <li className="space-y-2 rounded-xl border p-4" key={event.id}><p className="font-medium">{event.official_date ?? 'Unknown date'} · {event.batting_team.display_name ?? 'Unknown batting team'}</p><p className="text-sm">{event.pitcher?.display_name ?? 'Unknown pitcher'} · {event.inning === null ? 'Inning unknown' : `Inning ${event.inning}`} · {event.half_inning.toLowerCase()}</p><Link className="inline-flex min-h-11 items-center underline" state={{ from }} to={`/games/${event.game_id}#hr-${event.id}`}>Open home run in game</Link>{event.provenance ? <p className="text-xs text-muted-foreground">Source: {event.provenance.source_label} · retrieved {event.provenance.retrieved_at}</p> : null}</li>)}</ol></section> : <EmptyState>No verified player home-run events are listed for this scope.</EmptyState>}<nav aria-label="Player home runs pagination" className="flex items-center justify-between gap-3"><p className="text-sm">Page {page} · {response.count} listed records</p><div className="flex gap-2"><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!response.previous} onClick={() => setSearch(updateUrlState(search, { hr_page: String(page - 1) }))} type="button">Previous</button><button className="min-h-11 rounded-md border px-4 disabled:opacity-50" disabled={!response.next} onClick={() => setSearch(updateUrlState(search, { hr_page: String(page + 1) }))} type="button">Next</button></div></nav><PlayerEvidence coverage={response.coverage} meta={response.meta} /></div> : null}</PlayerQueryState>
}
