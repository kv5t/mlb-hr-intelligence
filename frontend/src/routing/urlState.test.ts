import { describe, expect, it } from 'vitest'

import { parseUrlState, updateUrlState } from './urlState'
import { UUIDS } from '@/test/fixtures'

describe('URL state', () => {
  it('restores deterministic shareable state', () => {
    const source = new URLSearchParams(`window=30G&season=2099&team=${UUIDS.teamA}&page=2`)
    const parsed = parseUrlState(source)
    expect(parsed.issues).toEqual([])
    expect(parsed.state).toMatchObject({ window: '30G', season: '2099', page: '2' })
    expect(parseUrlState(new URLSearchParams(parsed.validParams)).state).toEqual(parsed.state)
  })

  it('does not silently reinterpret invalid enum, date or UUID values', () => {
    const parsed = parseUrlState(new URLSearchParams('window=31G&date=2099-99-99&team=bad'))
    expect(parsed.state).toEqual({})
    expect(parsed.issues.map(({ key }) => key).sort()).toEqual(['date', 'team', 'window'])
  })

  it('supports page reset when a filter changes', () => {
    const next = updateUrlState(new URLSearchParams('season=2099&page=4'), { search: 'slugger' }, { resetPage: true })
    expect(next.get('page')).toBe('1')
    expect(next.get('search')).toBe('slugger')
  })

  it('rejects globally known parameters when a route does not support them', () => {
    expect(parseUrlState(new URLSearchParams('status=COMPLETED'), 'today').issues).toHaveLength(1)
    expect(parseUrlState(new URLSearchParams('window=7G'), 'games').issues).toHaveLength(1)
    expect(parseUrlState(new URLSearchParams('ordering=garbage'), 'games').issues).toHaveLength(1)
  })

  it('rejects URL values that API parameter schemas reject', () => {
    for (const query of ['season=0000', 'search=%20', 'position=%20']) {
      const parsed = parseUrlState(new URLSearchParams(query), 'players')
      expect(parsed.state).toEqual({})
      expect(parsed.issues).toHaveLength(1)
    }
    expect(parseUrlState(new URLSearchParams('season=2099&search=Fixture&position=1B'), 'players').issues).toEqual([])
  })

  it('rejects duplicates and restores independent player section pages', () => {
    expect(parseUrlState(new URLSearchParams('season=2099&season=2098'), 'players').issues).toHaveLength(1)
    const source = new URLSearchParams('season=2099&discovery_page=2&comparison_page=3')
    const restored = parseUrlState(new URLSearchParams(parseUrlState(source, 'players').validParams), 'players')
    expect(restored.state).toMatchObject({ discovery_page: '2', comparison_page: '3' })
  })

  it('validates Teams and restores independent Team Detail tab pages', () => {
    expect(parseUrlState(new URLSearchParams('season=2099&league=AL&division=East&search=Synthetic&ordering=name&page=2'), 'teams').issues).toEqual([])
    expect(parseUrlState(new URLSearchParams('season=2099&window=7G'), 'teams').issues).toHaveLength(1)
    const source = new URLSearchParams('season=2099&tab=hr-log&discovery_page=2&comparison_page=3&games_page=4&hr_page=5')
    const parsed = parseUrlState(source, 'teamDetail')
    expect(parsed.issues).toEqual([])
    expect(parseUrlState(new URLSearchParams(parsed.validParams), 'teamDetail').state).toMatchObject({
      discovery_page: '2', comparison_page: '3', games_page: '4', hr_page: '5', tab: 'hr-log',
    })
    expect(parseUrlState(new URLSearchParams('season=2099&tab=recurrence'), 'teamDetail').issues).toHaveLength(1)
  })
})
