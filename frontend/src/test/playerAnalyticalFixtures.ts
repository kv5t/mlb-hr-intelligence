import { meta, player, team, UUIDS, valueMetric } from './fixtures'

export const playerMetricIds = ['hr', 'pa', 'hr_per_pa', 'pa_per_hr', 'hr_per_game', 'hr_games', 'hr_game_pct', 'multi_hr_games', 'avg_hr_gap_games', 'median_hr_gap_games', 'current_hr_drought_games', 'max_hr_drought_games', 'current_hr_drought_pa', 'max_hr_drought_pa', 'current_hr_streak_games', 'max_hr_streak_games']
export const playerMetrics = Object.fromEntries(playerMetricIds.map((id) => [`player.${id}`, { ...valueMetric, unit: id.includes('pa') ? 'PA' : id.includes('hr_') ? 'BATTING_GAMES' : 'HR' }]))
playerMetrics['player.current_hr_drought_games'] = { ...valueMetric, value: 11, numerator: 11, unit: 'BATTING_GAMES' }
export const playerScope = {
  season: 2099, subject: 'PLAYER', subject_id: UUIDS.player, game_type: 'REGULAR', window: '7G', requested_n: 7, cutoff_date: '2099-04-03', cutoff_source: 'EXPLICIT', team_filter_id: null, home_away: 'ALL', selection_state: 'VALUE', actual_game_count: 3, known_eligible_game_count: 3,
}
export const playerDetail = {
  player, metrics: playerMetrics, scope: playerScope,
  coverage: [{ domain: 'HR_EVENTS', state: 'COMPLETE', reason_codes: [] }], meta,
}
export const otherGame = '77777777-7777-4777-8777-777777777777'
export const playerRecurrence = {
  ...playerDetail,
  observations: [
    { game_id: otherGame, official_date: '2099-04-02', represented_teams: [team()], pa: { ...valueMetric, value: 4, unit: 'PA' }, hr: valueMetric },
    { game_id: UUIDS.game, official_date: '2099-04-01', represented_teams: [{ ...team(UUIDS.teamB), display_name: 'Historical B' }], pa: { ...valueMetric, value: 5, unit: 'PA' }, hr: { ...valueMetric, value: 2 } },
  ],
  gaps: [
    { from_game_id: otherGame, to_game_id: UUIDS.game, non_hr_games: { ...valueMetric, unit: 'BATTING_GAMES' } },
    { from_game_id: UUIDS.game, to_game_id: otherGame, non_hr_games: { ...valueMetric, value: 2, unit: 'BATTING_GAMES' } },
  ],
}
export const hrEvent = {
  id: '88888888-8888-4888-8888-888888888888', game_id: UUIDS.game, plate_appearance_id: '99999999-9999-4999-8999-999999999999', official_date: '2099-04-01', batter: player, pitcher: null, batting_team: team(), inning: 2, half_inning: 'BOTTOM', game_pa_ordinal: 4, provenance: { source_label: 'Synthetic public evidence', retrieved_at: meta.data_as_of },
}
export const playerHomeRuns = {
  player, scope: playerScope, coverage: playerDetail.coverage, meta,
  count: 3, next: '/api/v1/players/id/home-runs/?page=2', previous: null,
  results: [hrEvent, { ...hrEvent, id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' }],
  total_hr: { ...valueMetric, state: 'INCOMPLETE', value: null, numerator: null, reason: 'SOURCE_TRUNCATED' },
}
export const analyticalSeasonPage = { count: 1, next: null, previous: null, results: [{ id: UUIDS.season, year: 2099, label: 'Synthetic 2099', starts_on: '2099-04-01', ends_on: '2099-10-31', status: 'COMPLETE' }], meta }
