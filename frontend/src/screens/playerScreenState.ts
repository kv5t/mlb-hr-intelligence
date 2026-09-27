import type { PlayerLeaderboardParams, PlayersParams } from '@/api'
import type { UrlState } from '@/routing/urlState'

export function leaderboardParams(state: UrlState, season: number): PlayerLeaderboardParams {
  return {
    season,
    window: state.window as PlayerLeaderboardParams['window'],
    team: state.team,
    home_away: state.home_away as PlayerLeaderboardParams['home_away'],
    cutoff: state.cutoff,
    search: state.search,
    position: state.position,
    bats: state.bats as PlayerLeaderboardParams['bats'],
    ordering: state.ordering as PlayerLeaderboardParams['ordering'],
    page: state.page ? Number(state.page) : undefined,
    page_size: state.page_size ? Number(state.page_size) : undefined,
  }
}

export function discoveryParams(state: UrlState, season: number): PlayersParams {
  return {
    season,
    team: state.team,
    search: state.search,
    position: state.position,
    bats: state.bats as PlayersParams['bats'],
    page: state.page ? Number(state.page) : undefined,
    page_size: state.page_size ? Number(state.page_size) : undefined,
  }
}
