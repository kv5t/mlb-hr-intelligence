import { z } from 'zod'

export const WINDOWS = ['7G', '15G', '30G', '60G', 'SEASON'] as const
export const GAME_STATUSES = [
  'SCHEDULED',
  'POSTPONED',
  'RESCHEDULED',
  'IN_PROGRESS',
  'SUSPENDED',
  'COMPLETED',
  'CANCELLED',
  'OTHER',
  'UNKNOWN',
] as const
export const GAME_ORDERINGS = [
  'official_date',
  '-official_date',
  'scheduled_start_at_utc',
  '-scheduled_start_at_utc',
] as const
export const HOME_AWAY = ['ALL', 'HOME', 'AWAY'] as const
export const PLAYER_LEADERBOARD_ORDERINGS = [
  'name', '-name',
  'hr', '-hr',
  'pa', '-pa',
  'hr_per_pa', '-hr_per_pa',
  'pa_per_hr', '-pa_per_hr',
  'hr_per_game', '-hr_per_game',
  'hr_game_pct', '-hr_game_pct',
  'median_hr_gap_games', '-median_hr_gap_games',
  'current_hr_drought_games', '-current_hr_drought_games',
  'current_hr_streak_games', '-current_hr_streak_games',
] as const

const pageFields = {
  page: z.number().int().positive().optional(),
  page_size: z.number().int().positive().max(100).optional(),
}
const year = z.number().int().min(1).max(9999)
const text = z.string().trim().min(1)
const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine((value) => {
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
})
const uuid = z.string().uuid()

export const isCanonicalUuid = (value: string) => uuid.safeParse(value).success

export const seasonsParamsSchema = z.object(pageFields)
export const teamsParamsSchema = z.object({
  season: year.optional(),
  league: text.optional(),
  division: text.optional(),
  search: text.optional(),
  ordering: z.enum(['name', '-name', 'abbreviation', '-abbreviation']).optional(),
  ...pageFields,
})
export const playersParamsSchema = z.object({
  season: year.optional(),
  team: uuid.optional(),
  search: text.optional(),
  position: text.optional(),
  bats: z.enum(['L', 'R', 'S', 'UNKNOWN']).optional(),
  ordering: z.enum(['name', '-name', 'position', '-position']).optional(),
  ...pageFields,
})
export const gamesParamsSchema = z.object({
  season: year.optional(),
  date_from: date.optional(),
  date_to: date.optional(),
  team: uuid.optional(),
  status: z.enum(GAME_STATUSES).optional(),
  ordering: z.enum(GAME_ORDERINGS).optional(),
  ...pageFields,
})
export const todayParamsSchema = z.object({
  season: year,
  date,
  window: z.enum(WINDOWS).optional(),
})
export const playerLeaderboardParamsSchema = z.object({
  season: year,
  window: z.enum(WINDOWS).optional(),
  team: uuid.optional(),
  home_away: z.enum(HOME_AWAY).optional(),
  cutoff: date.optional(),
  search: text.optional(),
  position: text.optional(),
  bats: z.enum(['L', 'R', 'S', 'UNKNOWN']).optional(),
  ordering: z.enum(PLAYER_LEADERBOARD_ORDERINGS).optional(),
  ...pageFields,
})
export const teamDetailParamsSchema = z.object({
  season: year,
  window: z.enum(WINDOWS).optional(),
  home_away: z.enum(HOME_AWAY).optional(),
  cutoff: date.optional(),
})
export const teamHomeRunsParamsSchema = teamDetailParamsSchema.extend({
  ordering: z.enum(['official_date', '-official_date']).optional(),
  ...pageFields,
})
export const teamRecurrenceParamsSchema = teamDetailParamsSchema

export type SeasonsParams = z.input<typeof seasonsParamsSchema>
export type TeamsParams = z.input<typeof teamsParamsSchema>
export type PlayersParams = z.input<typeof playersParamsSchema>
export type GamesParams = z.input<typeof gamesParamsSchema>
export type TodayParams = z.input<typeof todayParamsSchema>
export type PlayerLeaderboardParams = z.input<typeof playerLeaderboardParamsSchema>
export type TeamDetailParams = z.input<typeof teamDetailParamsSchema>
export type TeamHomeRunsParams = z.input<typeof teamHomeRunsParamsSchema>
export type TeamRecurrenceParams = z.input<typeof teamRecurrenceParamsSchema>

type ParamsSchema = z.ZodObject<z.ZodRawShape>

function normalize<T extends ParamsSchema>(schema: T, value: unknown): z.output<T> {
  const parsed = schema.parse(value)
  return Object.fromEntries(
    Object.entries(parsed).sort(([left], [right]) => left.localeCompare(right)),
  ) as z.output<T>
}

export const normalizeSeasonsParams = (value: unknown = {}) => normalize(seasonsParamsSchema, value)
export const normalizeTeamsParams = (value: unknown = {}) => normalize(teamsParamsSchema, value)
export const normalizePlayersParams = (value: unknown = {}) => normalize(playersParamsSchema, value)
export const normalizeGamesParams = (value: unknown = {}) => normalize(gamesParamsSchema, value)
export const normalizeTodayParams = (value: unknown) => normalize(todayParamsSchema, value)
export const normalizePlayerLeaderboardParams = (value: unknown) =>
  normalize(playerLeaderboardParamsSchema, value)
export const normalizeTeamDetailParams = (value: unknown) => normalize(teamDetailParamsSchema, value)
export const normalizeTeamHomeRunsParams = (value: unknown) => normalize(teamHomeRunsParamsSchema, value)
export const normalizeTeamRecurrenceParams = (value: unknown) => normalize(teamRecurrenceParamsSchema, value)

export function queryString(params: Record<string, unknown>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params).sort(([a], [b]) => a.localeCompare(b))) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  return query.toString()
}
