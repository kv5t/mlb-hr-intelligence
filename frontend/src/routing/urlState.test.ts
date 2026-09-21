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
})
