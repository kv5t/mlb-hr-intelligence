import type { PlayerDetailParams } from '@/api'
import type { UrlState } from '@/routing/urlState'

export function playerAnalyticalParams(state: UrlState): PlayerDetailParams {
  return { season: Number(state.season), window: state.window as PlayerDetailParams['window'], team: state.team, home_away: state.home_away as PlayerDetailParams['home_away'], cutoff: state.cutoff }
}

export function playerScopeSearch(state: UrlState) {
  const query = new URLSearchParams()
  for (const key of ['season', 'window', 'team', 'home_away', 'cutoff'] as const) {
    if (state[key]) query.set(key, state[key])
  }
  query.sort()
  return query.toString()
}
