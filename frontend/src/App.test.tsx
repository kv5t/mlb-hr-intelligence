import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('application shell', () => {
  it('exposes core navigation, active state and unavailable future destinations', () => {
    render(<MemoryRouter initialEntries={['/teams']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Teams' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Today/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /Teams, current page/ }).every((link) => link.getAttribute('aria-current') === 'page')).toBe(true)
    expect(screen.queryByRole('link', { name: 'Matchup' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Matchup').every((node) => node.getAttribute('aria-disabled') === 'true')).toBe(true)
  })

  it('has an accessible mobile More menu', () => {
    render(<MemoryRouter initialEntries={['/today']}><App /></MemoryRouter>)
    const more = screen.getByRole('button', { name: 'More navigation' })
    expect(more).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByRole('link', { name: /Games/ }).length).toBeGreaterThan(0)
  })

  it('shows invalid URL state with a recoverable action', () => {
    render(<MemoryRouter initialEntries={['/players?window=bad']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove invalid filters' })).toBeInTheDocument()
  })
})
