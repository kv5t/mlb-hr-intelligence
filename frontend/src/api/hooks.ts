import { useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import {
  normalizeGamesParams,
  normalizePlayersParams,
  normalizePlayerLeaderboardParams,
  normalizeSeasonsParams,
  normalizeTeamsParams,
  normalizeTodayParams,
  normalizeTeamDetailParams,
  normalizeTeamHomeRunsParams,
  type GamesParams,
  type PlayersParams,
  type PlayerLeaderboardParams,
  type SeasonsParams,
  type TeamsParams,
  type TodayParams,
  type TeamDetailParams,
  type TeamHomeRunsParams,
} from './params'
import { queryKeys } from './queryKeys'
import {
  gameDetailSchema,
  gamesResponseSchema,
  playersResponseSchema,
  playerLeaderboardResponseSchema,
  seasonsResponseSchema,
  teamsResponseSchema,
  todayResponseSchema,
  teamDetailSchema,
  teamHomeRunsResponseSchema,
} from './schemas'

const staleTime = 30_000

export function useSeasons(params: SeasonsParams = {}) {
  const normalized = normalizeSeasonsParams(params)
  return useQuery({
    queryKey: queryKeys.seasons(normalized),
    queryFn: ({ signal }) => apiGet({ path: 'seasons/', params: normalized, schema: seasonsResponseSchema, signal }),
    staleTime,
  })
}

export function useTeams(params: TeamsParams = {}) {
  const normalized = normalizeTeamsParams(params)
  return useQuery({
    queryKey: queryKeys.teams(normalized),
    queryFn: ({ signal }) => apiGet({ path: 'teams/', params: normalized, schema: teamsResponseSchema, signal }),
    staleTime,
  })
}

export function usePlayers(params: PlayersParams = {}) {
  const normalized = normalizePlayersParams(params)
  return useQuery({
    queryKey: queryKeys.players(normalized),
    queryFn: ({ signal }) => apiGet({ path: 'players/', params: normalized, schema: playersResponseSchema, signal }),
    staleTime,
  })
}

export function usePlayerLeaderboard(params: PlayerLeaderboardParams) {
  const normalized = normalizePlayerLeaderboardParams(params)
  return useQuery({
    queryKey: queryKeys.playerLeaderboard(normalized),
    queryFn: ({ signal }) => apiGet({
      path: 'leaderboards/players/',
      params: normalized,
      schema: playerLeaderboardResponseSchema,
      signal,
    }),
    staleTime,
  })
}

export function useGames(params: GamesParams = {}) {
  const normalized = normalizeGamesParams(params)
  return useQuery({
    queryKey: queryKeys.games(normalized),
    queryFn: ({ signal }) => apiGet({ path: 'games/', params: normalized, schema: gamesResponseSchema, signal }),
    staleTime,
  })
}

export function useGame(id: string) {
  return useQuery({
    queryKey: queryKeys.game(id),
    queryFn: ({ signal }) => apiGet({ path: `games/${id}/`, schema: gameDetailSchema, signal }),
    staleTime,
    enabled: id.length > 0,
  })
}

export function useToday(params: TodayParams) {
  const normalized = normalizeTodayParams(params)
  return useQuery({
    queryKey: queryKeys.today(normalized),
    queryFn: ({ signal }) => apiGet({ path: 'today/', params: normalized, schema: todayResponseSchema, signal }),
    staleTime,
  })
}

export function useTeamDetail(id: string, params: TeamDetailParams) {
  const normalized = normalizeTeamDetailParams(params)
  return useQuery({
    queryKey: queryKeys.teamDetail(id, normalized),
    queryFn: ({ signal }) => apiGet({ path: `teams/${id}/`, params: normalized, schema: teamDetailSchema, signal }),
    staleTime,
    enabled: id.length > 0,
  })
}

export function useTeamHomeRuns(id: string, params: TeamHomeRunsParams) {
  const normalized = normalizeTeamHomeRunsParams(params)
  return useQuery({
    queryKey: queryKeys.teamHomeRuns(id, normalized),
    queryFn: ({ signal }) => apiGet({ path: `teams/${id}/home-runs/`, params: normalized, schema: teamHomeRunsResponseSchema, signal }),
    staleTime,
    enabled: id.length > 0,
  })
}
