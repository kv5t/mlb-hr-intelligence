import {
  normalizeGamesParams,
  normalizePlayersParams,
  normalizeSeasonsParams,
  normalizeTeamsParams,
  normalizeTodayParams,
  type GamesParams,
  type PlayersParams,
  type SeasonsParams,
  type TeamsParams,
  type TodayParams,
} from './params'

export const queryKeys = {
  seasons: (params: SeasonsParams = {}) => ['v1', 'seasons', normalizeSeasonsParams(params)] as const,
  teams: (params: TeamsParams = {}) => ['v1', 'teams', normalizeTeamsParams(params)] as const,
  players: (params: PlayersParams = {}) => ['v1', 'players', normalizePlayersParams(params)] as const,
  games: (params: GamesParams = {}) => ['v1', 'games', normalizeGamesParams(params)] as const,
  game: (id: string) => ['v1', 'game', id] as const,
  today: (params: TodayParams) => ['v1', 'today', normalizeTodayParams(params)] as const,
}
