import { z } from 'zod'

import { GAME_ORDERINGS, GAME_STATUSES, WINDOWS } from '@/api/params'

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine((value) => {
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
})
const definitions = {
  season: z.string().regex(/^\d{4}$/),
  window: z.enum(WINDOWS),
  cutoff: date,
  team: z.string().uuid(),
  home_away: z.enum(['ALL', 'HOME', 'AWAY']),
  search: z.string().min(1),
  position: z.string().min(1),
  bats: z.enum(['L', 'R', 'S', 'UNKNOWN']),
  ordering: z.string().min(1),
  page: z.string().regex(/^[1-9]\d*$/),
  page_size: z.string().regex(/^[1-9]\d*$/).refine((value) => Number(value) <= 100),
  date,
  date_from: date,
  date_to: date,
  status: z.enum(GAME_STATUSES),
} as const

export type RouteSearchScope = 'today' | 'games' | 'gameDetail' | 'generic'
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
