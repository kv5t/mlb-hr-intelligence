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

export const baseWindowScopeSchema = z.object({
  season: z.number().int(),
  subject: z.enum(['PLAYER', 'TEAM']),
  game_type: z.literal('REGULAR'),
  window: z.enum(['7G', '15G', '30G', '60G', 'SEASON']),
  requested_n: z.number().int().nullable(),
  cutoff_date: isoDate.nullable(),
  cutoff_source: z.enum(['EXPLICIT', 'LATEST']),
})

export const windowScopeSchema = baseWindowScopeSchema.extend({
  subject: z.literal('PLAYER'),
})

const resolvedScopeFields = {
  subject_id: uuid,
  team_filter_id: uuid.nullable(),
  home_away: z.enum(['ALL', 'HOME', 'AWAY']),
  selection_state: z.enum(['VALUE', 'UNKNOWN', 'INCOMPLETE', 'ORDER_UNVERIFIED']),
  actual_game_count: z.number().int().nullable(),
  known_eligible_game_count: z.number().int().nonnegative(),
} as const

export const leaderScopeSchema = windowScopeSchema.extend(resolvedScopeFields)
export const teamWindowScopeSchema = baseWindowScopeSchema.extend({
  subject: z.literal('TEAM'),
  ...resolvedScopeFields,
  team_filter_id: z.null(),
})

const requiredLeaderboardMetricsSchema = z.object({
  'player.hr': metricValueSchema,
  'player.pa': metricValueSchema,
  'player.hr_per_pa': metricValueSchema,
  'player.pa_per_hr': metricValueSchema,
  'player.hr_per_game': metricValueSchema,
  'player.hr_game_pct': metricValueSchema,
  'player.median_hr_gap_games': metricValueSchema,
  'player.current_hr_drought_games': metricValueSchema,
}).catchall(metricValueSchema)

export const leaderboardRowSchema = z.object({
  player: playerSummarySchema,
  metrics: requiredLeaderboardMetricsSchema,
  scope: leaderScopeSchema,
  coverage: z.array(coverageSummarySchema),
})

export const todayLeaderSchema = leaderboardRowSchema
export const playerLeaderboardResponseSchema = paginatedSchema(leaderboardRowSchema)

export const requiredTeamMetricsSchema = z.object({
  'team.hr': metricValueSchema,
  'team.pa': metricValueSchema,
  'team.hr_per_pa': metricValueSchema,
  'team.pa_per_hr': metricValueSchema,
  'team.hr_per_game': metricValueSchema,
  'team.hr_games': metricValueSchema,
  'team.hr_game_pct': metricValueSchema,
  'team.multi_hr_games': metricValueSchema,
  'team.avg_hr_gap_games': metricValueSchema,
  'team.median_hr_gap_games': metricValueSchema,
  'team.current_hr_drought_games': metricValueSchema,
  'team.max_hr_drought_games': metricValueSchema,
  'team.current_hr_streak_games': metricValueSchema,
  'team.max_hr_streak_games': metricValueSchema,
}).catchall(metricValueSchema)

export const teamDetailSchema = z.object({
  team: teamSummarySchema,
  metrics: requiredTeamMetricsSchema,
  scope: teamWindowScopeSchema,
  coverage: z.array(coverageSummarySchema),
  meta: metaSchema,
})

export const teamHomeRunsResponseSchema = paginatedSchema(homeRunEventSummarySchema).extend({
  team: teamSummarySchema,
  total_hr: metricValueSchema,
  scope: teamWindowScopeSchema,
  coverage: z.array(coverageSummarySchema),
})

const matrixReason = z.string().nullable()
const noMatrixEvents = z.array(uuid).length(0)

const hrCountCellSchema = z.object({
  state: z.literal('HR_COUNT'),
  hr_count: z.number().int().min(1),
  home_run_event_ids: z.array(uuid).min(1),
  reason: matrixReason,
})

const knownZeroCellSchema = z.object({
  state: z.literal('KNOWN_ZERO'),
  hr_count: z.literal(0),
  home_run_event_ids: noMatrixEvents,
  reason: matrixReason,
})

const nonnumericMatrixCell = <State extends 'DNP' | 'ZERO_PA_APPEARANCE' | 'NOT_WITH_TEAM' | 'UNKNOWN' | 'INCOMPLETE'>(state: State) => z.object({
  state: z.literal(state),
  hr_count: z.null(),
  home_run_event_ids: noMatrixEvents,
  reason: matrixReason,
})

export const matrixCellSchema = z.discriminatedUnion('state', [
  hrCountCellSchema,
  knownZeroCellSchema,
  nonnumericMatrixCell('DNP'),
  nonnumericMatrixCell('ZERO_PA_APPEARANCE'),
  nonnumericMatrixCell('NOT_WITH_TEAM'),
  nonnumericMatrixCell('UNKNOWN'),
  nonnumericMatrixCell('INCOMPLETE'),
]).superRefine((cell, context) => {
  if (cell.state === 'HR_COUNT' && cell.home_run_event_ids.length !== cell.hr_count) {
    context.addIssue({
      code: 'custom',
      path: ['home_run_event_ids'],
      message: 'HR event IDs must match the HR count',
    })
  }
})

export const matrixColumnSchema = z.object({
  game_id: uuid,
  official_date: isoDate,
  scheduled_game_number: z.number().int().positive().nullable(),
  opponent: teamSummarySchema,
  home_away: z.enum(['HOME', 'AWAY']),
  game_status: z.enum([
    'SCHEDULED', 'POSTPONED', 'RESCHEDULED', 'IN_PROGRESS', 'SUSPENDED',
    'COMPLETED', 'CANCELLED', 'OTHER', 'UNKNOWN',
  ]),
  coverage: z.array(coverageSummarySchema),
})

export const matrixPlayerRowSchema = z.object({
  player: playerSummarySchema,
  player_season_hr: metricValueSchema,
  window_hr: metricValueSchema,
  cells: z.array(matrixCellSchema),
})

export const teamRecurrenceResponseSchema = z.object({
  team: teamSummarySchema,
  scope: teamWindowScopeSchema,
  metrics: requiredTeamMetricsSchema,
  columns: z.array(matrixColumnSchema),
  rows: z.array(matrixPlayerRowSchema),
  coverage: z.array(coverageSummarySchema),
  meta: metaSchema,
}).superRefine((response, context) => {
  const gameIds = response.columns.map((column) => column.game_id)
  if (new Set(gameIds).size !== gameIds.length) {
    context.addIssue({ code: 'custom', path: ['columns'], message: 'Game IDs must be unique' })
  }
  response.rows.forEach((row, index) => {
    if (row.cells.length !== response.columns.length) {
      context.addIssue({
        code: 'custom',
        path: ['rows', index, 'cells'],
        message: 'Matrix cells must align with columns',
      })
    }
  })
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
