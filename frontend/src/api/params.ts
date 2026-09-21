import { z } from 'zod'

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
  status: z
    .enum([
      'SCHEDULED',
      'POSTPONED',
      'RESCHEDULED',
      'IN_PROGRESS',
      'SUSPENDED',
      'COMPLETED',
      'CANCELLED',
      'OTHER',
      'UNKNOWN',
    ])
    .optional(),
  ordering: z
    .enum([
      'official_date',
      '-official_date',
      'scheduled_start_at_utc',
      '-scheduled_start_at_utc',
    ])
    .optional(),
  ...pageFields,
})
export const todayParamsSchema = z.object({
  season: year,
  date,
  window: z.enum(['7G', '15G', '30G', '60G', 'SEASON']).optional(),
})

export type SeasonsParams = z.input<typeof seasonsParamsSchema>
export type TeamsParams = z.input<typeof teamsParamsSchema>
export type PlayersParams = z.input<typeof playersParamsSchema>
export type GamesParams = z.input<typeof gamesParamsSchema>
export type TodayParams = z.input<typeof todayParamsSchema>

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

export function queryString(params: Record<string, unknown>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params).sort(([a], [b]) => a.localeCompare(b))) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  return query.toString()
}
