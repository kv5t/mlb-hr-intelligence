import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api'
import { EmptyState, ErrorState, InitialLoading, PartialDataNotice, RefreshingStatus } from './PageStates'

describe('shared page states', () => {
  it('announces loading, refreshing, empty and partial states', () => {
    const { rerender } = render(<InitialLoading />)
    expect(screen.getByText('Loading…')).toBeVisible()
    rerender(<RefreshingStatus />)
    expect(screen.getByText(/Refreshing current scope/)).toBeVisible()
    rerender(<EmptyState />)
    expect(screen.getByText(/No results/)).toBeVisible()
    rerender(<PartialDataNotice />)
    expect(screen.getByRole('status')).toHaveTextContent('partial')
  })

  it('distinguishes invalid, missing and unavailable API errors', () => {
    const error = new ApiClientError({ kind: 'api', status: 503, code: 'REVISION_UNAVAILABLE', message: 'Try later' })
    render(<ErrorState error={error} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Service temporarily unavailable')
  })

  it('offers retry for transient failures but not invalid requests', () => {
    const retry = vi.fn()
    const { rerender } = render(<ErrorState error={new ApiClientError({ kind: 'api', status: 503, code: 'UNAVAILABLE', message: 'Unavailable' })} onRetry={retry} />)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(retry).toHaveBeenCalledOnce()
    rerender(<ErrorState error={new ApiClientError({ kind: 'api', status: 400, code: 'INVALID', message: 'Invalid' })} onRetry={retry} />)
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })
})
