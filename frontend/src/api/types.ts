import type { z } from 'zod'

import type {
  coverageSummarySchema,
  gameDetailSchema,
  gameSummarySchema,
  gamesResponseSchema,
  metaSchema,
  metricValueSchema,
  playerSummarySchema,
  playersResponseSchema,
  leaderboardRowSchema,
  playerLeaderboardResponseSchema,
  seasonSummarySchema,
  seasonsResponseSchema,
  teamSummarySchema,
  teamsResponseSchema,
  todayResponseSchema,
  teamDetailSchema,
  teamHomeRunsResponseSchema,
  teamWindowScopeSchema,
  teamRecurrenceResponseSchema,
  matrixCellSchema,
  matrixColumnSchema,
  matrixPlayerRowSchema,
} from './schemas'

export type Meta = z.infer<typeof metaSchema>
export type MetricValue = z.infer<typeof metricValueSchema>
export type SeasonSummary = z.infer<typeof seasonSummarySchema>
export type TeamSummary = z.infer<typeof teamSummarySchema>
export type PlayerSummary = z.infer<typeof playerSummarySchema>
export type GameSummary = z.infer<typeof gameSummarySchema>
export type CoverageSummary = z.infer<typeof coverageSummarySchema>
export type GameDetail = z.infer<typeof gameDetailSchema>
export type SeasonsResponse = z.infer<typeof seasonsResponseSchema>
export type TeamsResponse = z.infer<typeof teamsResponseSchema>
export type PlayersResponse = z.infer<typeof playersResponseSchema>
export type LeaderboardRow = z.infer<typeof leaderboardRowSchema>
export type PlayerLeaderboardResponse = z.infer<typeof playerLeaderboardResponseSchema>
export type GamesResponse = z.infer<typeof gamesResponseSchema>
export type TodayResponse = z.infer<typeof todayResponseSchema>
export type TeamWindowScope = z.infer<typeof teamWindowScopeSchema>
export type TeamDetail = z.infer<typeof teamDetailSchema>
export type TeamHomeRunsResponse = z.infer<typeof teamHomeRunsResponseSchema>
export type TeamRecurrenceResponse = z.infer<typeof teamRecurrenceResponseSchema>
export type MatrixCell = z.infer<typeof matrixCellSchema>
export type MatrixColumn = z.infer<typeof matrixColumnSchema>
export type MatrixPlayerRow = z.infer<typeof matrixPlayerRowSchema>
