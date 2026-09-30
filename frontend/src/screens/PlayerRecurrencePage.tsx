import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { usePlayerRecurrence } from '@/api'
import { EmptyState } from '@/components/PageStates'
import { MetricValueView } from '@/components/MetricValueView'
import { parseUrlState } from '@/routing/urlState'
import { playerAnalyticalParams } from './playerAnalyticalState'
import { PlayerScopeBoundary, PlayerHeader, PlayerFilters, PlayerScopeSummary, PlayerEvidence, PlayerMetricGroup, PlayerQueryState, PlayerUnresolved } from './PlayerAnalyticalLayout'

export function PlayerRecurrencePage() {
  return <PlayerScopeBoundary route="playerRecurrence"><PlayerRecurrenceContent /></PlayerScopeBoundary>
}
function PlayerRecurrenceContent() {
  const { playerId = '' } = useParams()
  const [search] = useSearchParams()
  const location = useLocation()
  const state = parseUrlState(search, 'playerRecurrence').state
  const query = usePlayerRecurrence(playerId, playerAnalyticalParams(state))
  const response = query.data
  const from = `${location.pathname}${location.search}`
  return <PlayerQueryState query={query}>{response ? <div className="space-y-6"><PlayerHeader player={response.player} state={state} title="Recurrence" /><PlayerFilters state={state} /><PlayerScopeSummary scope={response.scope} /><PlayerMetricGroup title="Recurrence summary" metrics={response.metrics} items={[
    ['player.hr_game_pct', 'Games With HR %'], ['player.avg_hr_gap_games', 'Average HR Gap'], ['player.median_hr_gap_games', 'Median HR Gap'], ['player.current_hr_drought_games', 'Current HR Drought — Batting Games'], ['player.max_hr_drought_games', 'Maximum HR Drought — Batting Games'], ['player.current_hr_streak_games', 'Current HR Streak'], ['player.max_hr_streak_games', 'Maximum HR Streak'], ['player.current_hr_drought_pa', 'Current HR Drought — PA'], ['player.max_hr_drought_pa', 'Maximum HR Drought — PA'],
  ]} />{response.scope.selection_state !== 'VALUE' ? <PlayerUnresolved scope={response.scope} /> : !response.observations.length ? <EmptyState>No eligible batting games in this resolved scope.</EmptyState> : <>
    <section aria-labelledby="player-strip-title"><h2 className="text-xl font-semibold" id="player-strip-title">Chronological HR strip</h2><ol className="mt-3 flex gap-2 overflow-x-auto pb-2">{response.observations.map((observation) => <li className="shrink-0 rounded-lg border p-3" key={observation.game_id}><Link className="inline-flex min-h-11 flex-col justify-center gap-2 underline" state={{ from }} to={`/games/${observation.game_id}`}><span className="text-xs">{observation.official_date}</span><MetricValueView label={`${observation.official_date} HR`} metric={observation.hr} /></Link></li>)}</ol></section>
    <section aria-labelledby="player-games-title"><h2 className="text-xl font-semibold" id="player-games-title">Batting-game observations</h2><div className="mt-3 overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><caption className="sr-only">Chronological player batting games and historical represented teams</caption><thead className="bg-muted/60"><tr>{['Game', 'Historically represented teams', 'PA', 'HR'].map((label) => <th className="px-4 py-3" key={label} scope="col">{label}</th>)}</tr></thead><tbody>{response.observations.map((observation) => <tr className="border-t" key={observation.game_id}><th className="px-4 py-3 font-medium" scope="row"><Link className="inline-flex min-h-11 items-center underline" state={{ from }} to={`/games/${observation.game_id}`}>{observation.official_date}</Link></th><td className="px-4 py-3">{observation.represented_teams.map((team) => team.display_name ?? team.id).join(', ') || 'Unknown team'}</td><td className="px-4 py-3"><MetricValueView label={`${observation.official_date} PA`} metric={observation.pa} /></td><td className="px-4 py-3"><MetricValueView label={`${observation.official_date} HR`} metric={observation.hr} /></td></tr>)}</tbody></table></div></section>
    <section aria-labelledby="player-gaps-title"><h2 className="text-xl font-semibold" id="player-gaps-title">HR gaps</h2><p className="mt-1 text-sm text-muted-foreground">Eligible batting games strictly between two HR games. Consecutive HR games have a gap of 0. Values are supplied by the server.</p>{response.gaps.length ? <ul className="mt-3 space-y-2">{response.gaps.map((gap, index) => <li className="flex flex-wrap items-center gap-3 rounded-lg border p-3" key={`${gap.from_game_id}:${gap.to_game_id}`}><Link className="inline-flex min-h-11 items-center underline" state={{ from }} to={`/games/${gap.from_game_id}`}>Gap {index + 1} start game</Link><span aria-hidden="true">→</span><Link className="inline-flex min-h-11 items-center underline" state={{ from }} to={`/games/${gap.to_game_id}`}>Gap {index + 1} end game</Link><MetricValueView label={`Gap ${index + 1} non-HR batting games`} metric={gap.non_hr_games} /></li>)}</ul> : <EmptyState>No resolved individual HR gaps are available. Summary metrics retain their own evidence states.</EmptyState>}</section>
  </>}<PlayerEvidence coverage={response.coverage} meta={response.meta} /></div> : null}</PlayerQueryState>
}
