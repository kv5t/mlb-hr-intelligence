import type { z } from 'zod'

import { ApiClientError, schemaError } from './errors'
import { apiErrorEnvelopeSchema } from './schemas'
import { queryString } from './params'

const API_BASE = '/api/v1/'

export async function apiGet<Schema extends z.ZodType>(options: {
  path: string
  params?: Record<string, unknown>
  schema: Schema
  signal?: AbortSignal
}): Promise<z.output<Schema>> {
  const suffix = options.params ? queryString(options.params) : ''
  const url = `${API_BASE}${options.path}${suffix ? `?${suffix}` : ''}`
  let response: Response
  try {
    response = await fetch(url, { method: 'GET', headers: { Accept: 'application/json' }, signal: options.signal })
  } catch (error) {
    throw new ApiClientError({
      kind: 'network',
      code: 'NETWORK_ERROR',
      message: 'The API could not be reached.',
      cause: error,
    })
  }

  let payload: unknown
  try {
    payload = JSON.parse(await response.text())
  } catch (error) {
    throw new ApiClientError({
      kind: 'malformed_json',
      status: response.status,
      code: 'MALFORMED_JSON',
      message: 'The API returned malformed JSON.',
      cause: error,
    })
  }

  if (!response.ok) {
    const parsed = apiErrorEnvelopeSchema.safeParse(payload)
    if (!parsed.success) {
      throw new ApiClientError({
        kind: 'api',
        status: response.status,
        code: 'INVALID_ERROR_RESPONSE',
        message: 'The API request failed with an invalid error payload.',
      })
    }
    throw new ApiClientError({
      kind: 'api',
      status: response.status,
      code: parsed.data.error.code,
      message: parsed.data.error.message,
      details: parsed.data.error.details,
      meta:
        parsed.data.meta.dataset_revision && parsed.data.meta.data_as_of
          ? {
              dataset_revision: parsed.data.meta.dataset_revision,
              data_as_of: parsed.data.meta.data_as_of,
            }
          : null,
    })
  }

  const parsed = options.schema.safeParse(payload)
  if (!parsed.success) throw schemaError(parsed.error)
  return parsed.data
}
