import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/renderApp'

describe('application shell', () => {
  it('exposes core navigation, active state and unavailable future destinations', () => {
    renderApp('/teams')
    expect(screen.getByRole('heading', { name: 'Teams' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Today/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /Teams, current page/ }).every((link) => link.getAttribute('aria-current') === 'page')).toBe(true)
    expect(screen.queryByRole('link', { name: 'Matchup' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Matchup').every((node) => node.getAttribute('aria-disabled') === 'true')).toBe(true)
  })

  it('has an accessible mobile More menu', () => {
    renderApp('/players')
    const more = screen.getByRole('button', { name: 'More navigation' })
    expect(more).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByRole('link', { name: /Games/ }).length).toBeGreaterThan(0)
  })

  it('closes More after navigation and returns focus on Escape', () => {
    renderApp('/players')
    const more = screen.getByRole('button', { name: 'More navigation' })
    fireEvent.click(more)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(more).toHaveFocus()
    expect(more).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(more)
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Mobile primary' })).getByRole('link', { name: 'Games' }))
    expect(more).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows invalid URL state with a recoverable action', () => {
    renderApp('/players?window=bad')
    expect(screen.getByRole('heading', { name: 'Some URL filters are invalid' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove invalid filters' })).toBeInTheDocument()
  })
})
