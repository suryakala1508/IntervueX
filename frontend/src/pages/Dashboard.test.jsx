import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import { renderWithProviders } from '../test/renderWithProviders'
import { api } from '../lib/api'

const EMPTY_DASHBOARD = {
  total_interviews: 0,
  completed_interviews: 0,
  total_answers: 0,
  average_score: null,
  best_score: null,
  rubric_averages: null,
  strongest_topics: [],
  weak_topics: [],
  progress: [],
  recent_interviews: [],
  latest_plan: null,
}

const POPULATED_DASHBOARD = {
  total_interviews: 3,
  completed_interviews: 2,
  total_answers: 14,
  average_score: 6.8,
  best_score: 8.2,
  rubric_averages: {
    correctness: 7.1,
    relevance: 8,
    clarity: 6.2,
    completeness: 5.9,
    communication: 7.4,
  },
  strongest_topics: [{ topic: 'REST APIs', average_score: 8.4, answer_count: 4 }],
  weak_topics: [{ topic: 'System design', average_score: 4.2, answer_count: 3 }],
  progress: [
    { interview_id: 'i1', completed_at: '2026-01-01T10:00:00Z', score: 5.4 },
    { interview_id: 'i2', completed_at: '2026-01-08T10:00:00Z', score: 8.2 },
  ],
  recent_interviews: [
    {
      id: 'i2',
      title: 'Northwind Labs - round 1',
      status: 'completed',
      job_description_id: null,
      planned_question_count: 6,
      current_difficulty: 'hard',
      overall_score: 8.2,
      summary: null,
      created_at: '2026-01-08T10:00:00Z',
      updated_at: '2026-01-08T10:30:00Z',
    },
  ],
  latest_plan: null,
}

describe('Dashboard', () => {
  it('invites a new user to start rather than showing empty charts', async () => {
    vi.spyOn(api.dashboard, 'get').mockResolvedValue(EMPTY_DASHBOARD)

    renderWithProviders(<Dashboard />)

    expect(await screen.findByText(/no interviews yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/rubric averages/i)).not.toBeInTheDocument()
  })

  it('summarises performance once there is history', async () => {
    vi.spyOn(api.dashboard, 'get').mockResolvedValue(POPULATED_DASHBOARD)

    renderWithProviders(<Dashboard />)

    expect(await screen.findByText('6.8/10')).toBeInTheDocument()
    expect(screen.getByText('8.2/10')).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText('System design')).toBeInTheDocument()
    expect(screen.getByText('REST APIs')).toBeInTheDocument()
    expect(screen.getByText('Northwind Labs - round 1')).toBeInTheDocument()
  })

  it('renders each rubric dimension as its own meter', async () => {
    vi.spyOn(api.dashboard, 'get').mockResolvedValue(POPULATED_DASHBOARD)

    renderWithProviders(<Dashboard />)

    expect(await screen.findByRole('meter', { name: 'Correctness' })).toHaveAttribute(
      'aria-valuenow',
      '7.1',
    )
    expect(screen.getByRole('meter', { name: 'Completeness' })).toHaveAttribute(
      'aria-valuenow',
      '5.9',
    )
  })

  it('shows the failure and a way to retry when loading fails', async () => {
    vi.spyOn(api.dashboard, 'get').mockRejectedValue(new Error('Could not reach the server'))

    renderWithProviders(<Dashboard />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
