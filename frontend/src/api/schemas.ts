import { z } from 'zod'

const uuid = z.string().uuid()
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine((value) => {
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
})
const isoInstant = z.string().datetime({ offset: true }).refine((value) => value.endsWith('Z'))

export const metaSchema = z.object({
  dataset_revision: z.string().min(1),
  data_as_of: isoInstant,
})

export const nullableMetaSchema = z.object({
  dataset_revision: z.string().nullable(),
  data_as_of: isoInstant.nullable(),
})

export const apiErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()),
  }),
  meta: nullableMetaSchema,
})

export const metricStateSchema = z.enum([
  'VALUE',
  'NOT_APPLICABLE',
  'UNKNOWN',
  'INCOMPLETE',
  'ORDER_UNVERIFIED',
  'INSUFFICIENT_HISTORY',
])

export const metricValueSchema = z
  .object({
    state: metricStateSchema,
    value: z.number().finite().nullable(),
    unit: z.string().nullable(),
    numerator: z.number().int().nonnegative().nullable(),
    denominator: z.number().int().nonnegative().nullable(),
    reason: z.string().nullable(),
  })
  .superRefine((metric, context) => {
    if (metric.state === 'VALUE' && metric.value === null) {
      context.addIssue({ code: 'custom', path: ['value'], message: 'VALUE requires a number' })
    }
    if (metric.state !== 'VALUE' && metric.value !== null) {
      context.addIssue({ code: 'custom', path: ['value'], message: 'Unavailable metrics require null' })
    }
  })

export const seasonSummarySchema = z.object({
  id: uuid,
  year: z.number().int(),
  label: z.string().nullable(),
  starts_on: isoDate.nullable(),
  ends_on: isoDate.nullable(),
  status: z.string().nullable(),
})

export const teamSummarySchema = z.object({
  id: uuid,
  mlb_id: z.number().int().nullable(),
  display_name: z.string().nullable(),
  abbreviation: z.string().nullable(),
  league: z.string().nullable(),
  division: z.string().nullable(),
})

export const playerSummarySchema = z.object({
  id: uuid,
  mlb_id: z.number().int().nullable(),
  display_name: z.string().nullable(),
  given_name: z.string().nullable(),
  family_name: z.string().nullable(),
  bats: z.enum(['L', 'R', 'S', 'UNKNOWN']),
  throws: z.enum(['L', 'R', 'UNKNOWN']),
  primary_position: z.string().nullable(),
  represented_team: teamSummarySchema.nullable(),
})

export const venueSummarySchema = z.object({
  id: uuid,
  name: z.string().nullable(),
  timezone_id: z.string().nullable(),
})

export const gameSummarySchema = z.object({
  id: uuid,
  mlb_game_pk: z.number().int().nullable(),
  season: z.number().int(),
  game_type: z.enum(['REGULAR', 'POSTSEASON', 'SPRING', 'ALL_STAR', 'OTHER', 'UNKNOWN']),
  official_date: isoDate.nullable(),
  scheduled_start_at_utc: isoInstant.nullable(),
  status: z.enum([
    'SCHEDULED',
    'POSTPONED',
    'RESCHEDULED',
    'IN_PROGRESS',
    'SUSPENDED',
    'COMPLETED',
    'CANCELLED',
    'OTHER',
    'UNKNOWN',
  ]),
  finality: z.enum(['FINAL', 'NOT_FINAL', 'UNKNOWN']),
  home_team: teamSummarySchema,
  away_team: teamSummarySchema,
  home_score: z.number().int().nullable(),
  away_score: z.number().int().nullable(),
  scheduled_game_number: z.number().int().nullable(),
  venue: venueSummarySchema.nullable(),
  hr_count: metricValueSchema,
})

export const coverageSummarySchema = z.object({
  domain: z.enum(['SCHEDULE', 'PARTICIPATION', 'PLATE_APPEARANCES', 'HR_EVENTS']),
  state: z.enum(['COMPLETE', 'PARTIAL', 'UNKNOWN', 'UNAVAILABLE']),
  reason_codes: z.array(z.string()),
})

export const participantSchema = z.object({
  player: playerSummarySchema,
  team: teamSummarySchema,
  participation_state: z.literal('APPEARED'),
  roles: z.array(z.enum(['BATTER', 'PITCHER', 'FIELDER'])),
  pa_count: metricValueSchema,
})

export const homeRunEventSummarySchema = z.object({
  id: uuid,
  game_id: uuid,
  plate_appearance_id: uuid,
  official_date: isoDate.nullable(),
  batter: playerSummarySchema,
  pitcher: playerSummarySchema.nullable(),
  batting_team: teamSummarySchema,
  inning: z.number().int().nullable(),
  half_inning: z.string(),
  game_pa_ordinal: z.number().int().nullable(),
  provenance: z
    .object({ source_label: z.string(), retrieved_at: isoInstant })
    .nullable(),
})

export const gameDetailSchema = z.object({
  game: gameSummarySchema,
  participants: z.array(participantSchema),
  home_runs: z.array(homeRunEventSummarySchema),
  coverage: z.array(coverageSummarySchema),
  meta: metaSchema,
})

export function paginatedSchema<Item extends z.ZodType>(item: Item) {
  return z.object({
    count: z.number().int().nonnegative(),
    next: z.string().nullable(),
    previous: z.string().nullable(),
    results: z.array(item),
    meta: metaSchema,
  })
}

export const seasonsResponseSchema = paginatedSchema(seasonSummarySchema)
export const teamsResponseSchema = paginatedSchema(teamSummarySchema)
export const playersResponseSchema = paginatedSchema(playerSummarySchema)
export const gamesResponseSchema = paginatedSchema(gameSummarySchema)

export const windowScopeSchema = z.object({
  season: z.number().int(),
  subject: z.literal('PLAYER'),
  game_type: z.literal('REGULAR'),
  window: z.enum(['7G', '15G', '30G', '60G', 'SEASON']),
  requested_n: z.number().int().nullable(),
  cutoff_date: isoDate,
  cutoff_source: z.literal('EXPLICIT'),
})

export const leaderScopeSchema = windowScopeSchema.extend({
  subject_id: uuid,
  team_filter_id: uuid.nullable(),
  home_away: z.enum(['ALL', 'HOME', 'AWAY']),
  selection_state: z.enum(['VALUE', 'UNKNOWN', 'INCOMPLETE', 'ORDER_UNVERIFIED']),
  actual_game_count: z.number().int().nullable(),
  known_eligible_game_count: z.number().int().nonnegative(),
})

export const todayLeaderSchema = z.object({
  player: playerSummarySchema,
  metrics: z.record(z.string(), metricValueSchema),
  scope: leaderScopeSchema,
  coverage: z.array(coverageSummarySchema),
})

export const todayResponseSchema = z.object({
  date: isoDate,
  games: z.array(gameSummarySchema),
  recent_leaders: z.array(todayLeaderSchema),
  recent_leaders_availability: z.object({
    state: z.enum(['VALUE', 'NOT_APPLICABLE', 'UNKNOWN', 'INCOMPLETE', 'ORDER_UNVERIFIED']),
    reason: z.string().nullable(),
  }),
  scope: windowScopeSchema,
  coverage: z.array(coverageSummarySchema),
  meta: metaSchema,
})
