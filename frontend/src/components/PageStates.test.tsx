import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

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
})
