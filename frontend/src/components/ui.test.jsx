import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ErrorNote, ScoreBadge, ScoreBar, formatDate, scoreTone, titleCase } from './ui'

describe('scoreTone', () => {
  it.each([
    [9, 'good'],
    [7.5, 'good'],
    [6, 'warn'],
    [5, 'warn'],
    [4.9, 'bad'],
    [0, 'bad'],
  ])('maps %s to the %s band', (score, expected) => {
    expect(scoreTone(score)).toBe(expected)
  })

  it('treats a missing score as neutral rather than failing', () => {
    expect(scoreTone(null)).toBe('ink')
    expect(scoreTone(undefined)).toBe('ink')
  })
})

describe('ScoreBadge', () => {
  it('shows the score out of ten', () => {
    render(<ScoreBadge score={7} />)
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('/10')).toBeInTheDocument()
  })

  it('shows a placeholder when there is no score', () => {
    render(<ScoreBadge score={null} />)
    expect(screen.getByText('--')).toBeInTheDocument()
  })
})

describe('ScoreBar', () => {
  it('exposes the value to assistive technology', () => {
    render(<ScoreBar label="Clarity" score={6} />)

    const meter = screen.getByRole('meter', { name: 'Clarity' })
    expect(meter).toHaveAttribute('aria-valuenow', '6')
    expect(meter).toHaveAttribute('aria-valuemin', '0')
    expect(meter).toHaveAttribute('aria-valuemax', '10')
  })

  it('reports zero rather than NaN for a missing score', () => {
    render(<ScoreBar label="Clarity" score={null} />)
    expect(screen.getByRole('meter', { name: 'Clarity' })).toHaveAttribute('aria-valuenow', '0')
  })
})

describe('ErrorNote', () => {
  it('renders nothing when there is no error', () => {
    const { container } = render(<ErrorNote error={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('accepts either an Error or a plain string', () => {
    const { rerender } = render(<ErrorNote error={new Error('Boom')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Boom')

    rerender(<ErrorNote error="Plain message" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Plain message')
  })
})

describe('formatting helpers', () => {
  it('turns an enum value into a readable label', () => {
    expect(titleCase('role_specific')).toBe('Role Specific')
    expect(titleCase('in_progress')).toBe('In Progress')
  })

  it('handles a missing value without throwing', () => {
    expect(titleCase(null)).toBe('')
    expect(formatDate(null)).toBe('--')
  })
})
