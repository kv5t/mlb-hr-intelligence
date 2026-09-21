import type { ReactNode } from 'react'

import { ApiClientError } from '@/api'

export function InitialLoading({ label = 'Loading' }: { label?: string }) {
  return <p aria-live="polite" className="text-sm text-muted-foreground">{label}…</p>
}

export function RefreshingStatus() {
  return <p aria-live="polite" className="text-sm text-muted-foreground">Refreshing current scope…</p>
}

export function EmptyState({ children = 'No results for this scope.' }: { children?: ReactNode }) {
  return <p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">{children}</p>
}

export function PartialDataNotice({ children = 'Some values use partial or unavailable evidence.' }: { children?: ReactNode }) {
  return <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">{children}</p>
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const clientError = error instanceof ApiClientError ? error : null
  const title =
    clientError?.status === 400 ? 'Invalid request' :
    clientError?.status === 404 ? 'Not found' :
    clientError?.status === 503 ? 'Service temporarily unavailable' :
    clientError?.kind === 'network' ? 'Network error' : 'Unable to load data'
  const message = clientError?.message ?? 'An unexpected error occurred.'
  return (
    <section role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-5">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      {onRetry && clientError?.status !== 400 && clientError?.status !== 404 ? (
        <button
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          onClick={onRetry}
          type="button"
        >
          Retry
        </button>
      ) : null}
    </section>
  )
}
