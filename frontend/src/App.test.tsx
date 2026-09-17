import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('frontend foundation', () => {
  it('mounts the application', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'MLB HR Intelligence' })).toBeInTheDocument()
  })
})
