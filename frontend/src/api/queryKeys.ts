import {
  normalizeGamesParams,
  normalizePlayersParams,
  normalizePlayerLeaderboardParams,
  normalizeSeasonsParams,
  normalizeTeamsParams,
  normalizeTodayParams,
  normalizeTeamDetailParams,
  normalizeTeamHomeRunsParams,
  normalizeTeamRecurrenceParams,
  type GamesParams,
  type PlayersParams,
  type PlayerLeaderboardParams,
  type SeasonsParams,
  type TeamsParams,
  type TodayParams,
  type TeamDetailParams,
  type TeamHomeRunsParams,
  type TeamRecurrenceParams,
} from './params'

export const queryKeys = {
  seasons: (params: SeasonsParams = {}) => ['v1', 'seasons', normalizeSeasonsParams(params)] as const,
  teams: (params: TeamsParams = {}) => ['v1', 'teams', normalizeTeamsParams(params)] as const,
  players: (params: PlayersParams = {}) => ['v1', 'players', normalizePlayersParams(params)] as const,
  playerLeaderboard: (params: PlayerLeaderboardParams) =>
    ['v1', 'leaderboard', 'players', normalizePlayerLeaderboardParams(params)] as const,
  games: (params: GamesParams = {}) => ['v1', 'games', normalizeGamesParams(params)] as const,
  game: (id: string) => ['v1', 'game', id] as const,
  today: (params: TodayParams) => ['v1', 'today', normalizeTodayParams(params)] as const,
  teamDetail: (id: string, params: TeamDetailParams) =>
    ['v1', 'team', id, normalizeTeamDetailParams(params)] as const,
  teamHomeRuns: (id: string, params: TeamHomeRunsParams) =>
    ['v1', 'team', id, 'home-runs', normalizeTeamHomeRunsParams(params)] as const,
  teamRecurrence: (id: string, params: TeamRecurrenceParams) =>
    ['v1', 'team', id, 'recurrence', normalizeTeamRecurrenceParams(params)] as const,
}
