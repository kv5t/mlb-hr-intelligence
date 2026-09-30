import { useParams, useSearchParams } from 'react-router-dom'
import { usePlayerDetail } from '@/api'
import { EmptyState, PartialDataNotice } from '@/components/PageStates'
import { parseUrlState } from '@/routing/urlState'
import { playerAnalyticalParams } from './playerAnalyticalState'
import { PlayerScopeBoundary, PlayerHeader, PlayerFilters, PlayerScopeSummary, PlayerEvidence, PlayerMetricGroup, PlayerQueryState } from './PlayerAnalyticalLayout'

export function PlayerDetailPage() {
  return <PlayerScopeBoundary route="playerDetail"><PlayerDetailContent /></PlayerScopeBoundary>
}
function PlayerDetailContent() {
  const { playerId = '' } = useParams()
  const [search] = useSearchParams()
  const state = parseUrlState(search, 'playerDetail').state
  const query = usePlayerDetail(playerId, playerAnalyticalParams(state))
  const detail = query.data
  return <PlayerQueryState query={query}>{detail ? <div className="space-y-6"><PlayerHeader player={detail.player} state={state} title="Overview" /><PlayerFilters state={state} /><PlayerScopeSummary scope={detail.scope} />{Object.values(detail.metrics).some((metric) => metric.state !== 'VALUE') ? <PartialDataNotice>Unavailable values retain their evidence state; they are never treated as zero.</PartialDataNotice> : null}{detail.scope.actual_game_count === 0 ? <EmptyState>No eligible batting games in this resolved scope.</EmptyState> : null}<PlayerMetricGroup title="Production" metrics={detail.metrics} items={[
    ['player.hr', 'HR'], ['player.pa', 'PA'], ['player.hr_per_pa', 'HR / PA'], ['player.pa_per_hr', 'PA / HR'], ['player.hr_per_game', 'HR / Batting Game'],
  ]} /><PlayerMetricGroup title="Frequency" metrics={detail.metrics} items={[
    ['player.hr_games', 'Games With HR'], ['player.hr_game_pct', 'Games With HR %'], ['player.multi_hr_games', 'Multi-HR Games'],
  ]} /><PlayerMetricGroup title="Recurrence" metrics={detail.metrics} items={[
    ['player.avg_hr_gap_games', 'Average HR Gap'], ['player.median_hr_gap_games', 'Median HR Gap'], ['player.current_hr_drought_games', 'Current HR Drought — Batting Games'], ['player.max_hr_drought_games', 'Maximum HR Drought — Batting Games'], ['player.current_hr_drought_pa', 'Current HR Drought — PA'], ['player.max_hr_drought_pa', 'Maximum HR Drought — PA'], ['player.current_hr_streak_games', 'Current HR Streak'], ['player.max_hr_streak_games', 'Maximum HR Streak'],
  ]} /><PlayerEvidence coverage={detail.coverage} meta={detail.meta} /></div> : null}</PlayerQueryState>
}
