import { z } from 'zod'

import {
  GAME_ORDERINGS,
  GAME_STATUSES,
  PLAYER_LEADERBOARD_ORDERINGS,
  WINDOWS,
} from '@/api/params'

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine((value) => {
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
})
const definitions = {
  season: z.string().regex(/^\d{4}$/).refine((value) => Number(value) >= 1),
  window: z.enum(WINDOWS),
  cutoff: date,
  team: z.string().uuid(),
  home_away: z.enum(['ALL', 'HOME', 'AWAY']),
  search: z.string().trim().min(1),
  position: z.string().trim().min(1),
  league: z.string().trim().min(1),
  division: z.string().trim().min(1),
  bats: z.enum(['L', 'R', 'S', 'UNKNOWN']),
  ordering: z.string().min(1),
  page: z.string().regex(/^[1-9]\d*$/),
  discovery_page: z.string().regex(/^[1-9]\d*$/),
  comparison_page: z.string().regex(/^[1-9]\d*$/),
  games_page: z.string().regex(/^[1-9]\d*$/),
  hr_page: z.string().regex(/^[1-9]\d*$/),
  hr_ordering: z.enum(['official_date', '-official_date']),
  row_order: z.enum(['season_hr_desc', 'window_hr_desc', 'name']),
  tab: z.enum(['overview', 'players', 'games', 'hr-log']),
  page_size: z.string().regex(/^[1-9]\d*$/).refine((value) => Number(value) <= 100),
  date,
  date_from: date,
  date_to: date,
  status: z.enum(GAME_STATUSES),
} as const

export type RouteSearchScope = 'today' | 'games' | 'gameDetail' | 'league' | 'players' | 'teams' | 'teamDetail' | 'teamRecurrence' | 'playerDetail' | 'playerRecurrence' | 'playerHomeRuns' | 'generic'
export type UrlStateKey = keyof typeof definitions

const routeDefinitions: Record<
  RouteSearchScope,
  Partial<Record<UrlStateKey, z.ZodType<string>>>
> = {
  today: { season: definitions.season, date: definitions.date, window: definitions.window },
  games: {
    season: definitions.season,
    date_from: definitions.date_from,
    date_to: definitions.date_to,
    team: definitions.team,
    status: definitions.status,
    ordering: z.enum(GAME_ORDERINGS),
    page: definitions.page,
    page_size: definitions.page_size,
  },
  gameDetail: {},
  league: {
    season: definitions.season,
    window: definitions.window,
    cutoff: definitions.cutoff,
    team: definitions.team,
    home_away: definitions.home_away,
    search: definitions.search,
    position: definitions.position,
    bats: definitions.bats,
    ordering: z.enum(PLAYER_LEADERBOARD_ORDERINGS),
    page: definitions.page,
    page_size: definitions.page_size,
  },
  players: {
    season: definitions.season,
    window: definitions.window,
    cutoff: definitions.cutoff,
    team: definitions.team,
    home_away: definitions.home_away,
    search: definitions.search,
    position: definitions.position,
    bats: definitions.bats,
    ordering: z.enum(PLAYER_LEADERBOARD_ORDERINGS),
    discovery_page: definitions.discovery_page,
    comparison_page: definitions.comparison_page,
    page_size: definitions.page_size,
  },
  teams: {
    season: definitions.season,
    league: definitions.league,
    division: definitions.division,
    search: definitions.search,
    ordering: z.enum(['name', '-name', 'abbreviation', '-abbreviation']),
    page: definitions.page,
    page_size: definitions.page_size,
  },
  teamDetail: {
    season: definitions.season,
    window: definitions.window,
    cutoff: definitions.cutoff,
    home_away: definitions.home_away,
    tab: definitions.tab,
    discovery_page: definitions.discovery_page,
    comparison_page: definitions.comparison_page,
    games_page: definitions.games_page,
    hr_page: definitions.hr_page,
    hr_ordering: definitions.hr_ordering,
    page_size: definitions.page_size,
  },
  teamRecurrence: {
    season: definitions.season,
    window: definitions.window,
    cutoff: definitions.cutoff,
    home_away: definitions.home_away,
    row_order: definitions.row_order,
  },
  playerDetail: { season: definitions.season, window: definitions.window, team: definitions.team, home_away: definitions.home_away, cutoff: definitions.cutoff },
  playerRecurrence: { season: definitions.season, window: definitions.window, team: definitions.team, home_away: definitions.home_away, cutoff: definitions.cutoff },
  playerHomeRuns: { season: definitions.season, window: definitions.window, team: definitions.team, home_away: definitions.home_away, cutoff: definitions.cutoff, hr_ordering: definitions.hr_ordering, hr_page: definitions.hr_page, page_size: definitions.page_size },
  generic: definitions,
}

export type UrlState = Partial<Record<UrlStateKey, string>>
export type UrlStateIssue = { key: string; value: string; message: string }

export type ParsedUrlState = {
  state: UrlState
  validParams: URLSearchParams
  issues: UrlStateIssue[]
}

export function parseUrlState(
  params: URLSearchParams,
  route: RouteSearchScope = 'generic',
): ParsedUrlState {
  const state: UrlState = {}
  const validParams = new URLSearchParams()
  const issues: UrlStateIssue[] = []
  const seen = new Set<string>()
  for (const [key, value] of params.entries()) {
    if (seen.has(key)) {
      issues.push({ key, value, message: 'Duplicate parameter' })
      validParams.delete(key)
      delete state[key as UrlStateKey]
      continue
    }
    seen.add(key)
    const schema = routeDefinitions[route][key as UrlStateKey]
    if (!schema) {
      issues.push({ key, value, message: 'Unsupported parameter' })
      continue
    }
    const result = schema.safeParse(value)
    if (!result.success) {
      issues.push({ key, value, message: 'Invalid value' })
      continue
    }
    state[key as UrlStateKey] = value
    validParams.set(key, value)
  }
  validParams.sort()
  return { state, validParams, issues }
}

export function updateUrlState(
  current: URLSearchParams,
  changes: Partial<Record<UrlStateKey, string | null | undefined>>,
  options: { resetPage?: boolean } = {},
): URLSearchParams {
  const next = new URLSearchParams(current)
  for (const [key, value] of Object.entries(changes)) {
    if (value === null || value === undefined || value === '') next.delete(key)
    else next.set(key, value)
  }
  if (options.resetPage) next.set('page', '1')
  next.sort()
  return next
}
