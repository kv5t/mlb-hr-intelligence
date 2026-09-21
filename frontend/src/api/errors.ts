import { ZodError } from 'zod'

import type { Meta } from './types'

export type ApiErrorKind = 'api' | 'network' | 'malformed_json' | 'schema'

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly code: string
  readonly details: Record<string, unknown>
  readonly meta: Meta | null

  constructor(options: {
    kind: ApiErrorKind
    message: string
    status?: number | null
    code: string
    details?: Record<string, unknown>
    meta?: Meta | null
    cause?: unknown
  }) {
    super(options.message, { cause: options.cause })
    this.name = 'ApiClientError'
    this.kind = options.kind
    this.status = options.status ?? null
    this.code = options.code
    this.details = options.details ?? {}
    this.meta = options.meta ?? null
  }
}

export function schemaError(error: ZodError): ApiClientError {
  return new ApiClientError({
    kind: 'schema',
    code: 'INVALID_RESPONSE_SCHEMA',
    message: 'The server response did not match the public API contract.',
    details: { issues: error.issues.map(({ path, message }) => ({ path, message })) },
    cause: error,
  })
}
