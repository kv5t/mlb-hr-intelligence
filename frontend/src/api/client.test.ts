import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiGet } from './client'
import { ApiClientError } from './errors'
import { seasonsResponseSchema } from './schemas'
import { meta } from '@/test/fixtures'

const success = { count: 0, next: null, previous: null, results: [], meta }

afterEach(() => vi.unstubAllGlobals())

describe('native fetch API client', () => {
  it('validates successful JSON and uses the relative v1 boundary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(success), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(apiGet({ path: 'seasons/', params: { page: 2 }, schema: seasonsResponseSchema })).resolves.toEqual(success)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/seasons/?page=2', expect.objectContaining({ method: 'GET' }))
  })

  it.each([400, 404, 503])('returns a typed %s API error', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: `E${status}`, message: 'Safe message', details: {} },
      meta,
    }), { status })))
    try {
      await apiGet({ path: 'seasons/', schema: seasonsResponseSchema })
      throw new Error('Expected rejection')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiClientError)
      expect(error).toMatchObject({ kind: 'api', status, code: `E${status}` })
    }
  })

  it('handles malformed error payloads without exposing response internals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"private":true}', { status: 400 })))
    await expect(apiGet({ path: 'seasons/', schema: seasonsResponseSchema })).rejects.toMatchObject({
      kind: 'api', code: 'INVALID_ERROR_RESPONSE', details: {},
    })
  })

  it('distinguishes network, malformed JSON and schema failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(apiGet({ path: 'seasons/', schema: seasonsResponseSchema })).rejects.toMatchObject({ kind: 'network' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not-json', { status: 200 })))
    await expect(apiGet({ path: 'seasons/', schema: seasonsResponseSchema })).rejects.toMatchObject({ kind: 'malformed_json' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...success, count: 'bad' }), { status: 200 })))
    await expect(apiGet({ path: 'seasons/', schema: seasonsResponseSchema })).rejects.toMatchObject({ kind: 'schema' })
  })
})
