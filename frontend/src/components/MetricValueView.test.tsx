import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MetricValueView } from './MetricValueView'
import type { MetricValue } from '@/api'

const metric = (state: MetricValue['state'], value: number | null = null, reason: string | null = null): MetricValue => ({
  state, value, unit: 'HR', numerator: value, denominator: null, reason,
})

describe('MetricValueView', () => {
  it('keeps numeric zero visible', () => {
    render(<MetricValueView label="Home runs" metric={metric('VALUE', 0)} />)
    expect(screen.getByText('0')).toBeVisible()
    expect(screen.getByLabelText(/Home runs: 0 HR/)).toBeInTheDocument()
  })

  it.each([
    ['UNKNOWN', 'Unknown'],
    ['INCOMPLETE', 'Partial data'],
    ['ORDER_UNVERIFIED', 'Order unverified'],
    ['INSUFFICIENT_HISTORY', 'Not enough history'],
  ] as const)('renders %s semantically', (state, text) => {
    render(<MetricValueView label="Metric" metric={metric(state)} />)
    expect(screen.getByText(text)).toBeVisible()
  })

  it('keeps a valid value when NO_HR_IN_SCOPE annotates it', () => {
    render(<MetricValueView label="Drought" metric={metric('VALUE', 4, 'NO_HR_IN_SCOPE')} />)
    expect(screen.getByText('4')).toBeVisible()
    expect(screen.getByLabelText(/No home runs in scope/)).toBeInTheDocument()
  })
})
