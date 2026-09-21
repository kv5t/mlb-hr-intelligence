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
  seasonSummarySchema,
  seasonsResponseSchema,
  teamSummarySchema,
  teamsResponseSchema,
  todayResponseSchema,
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
export type GamesResponse = z.infer<typeof gamesResponseSchema>
export type TodayResponse = z.infer<typeof todayResponseSchema>
