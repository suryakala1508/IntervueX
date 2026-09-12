import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InterviewRoom from './InterviewRoom'
import { renderWithProviders } from '../test/renderWithProviders'
import { api } from '../lib/api'

const QUESTION = {
  id: 'q1',
  position: 1,
  category: 'technical',
  difficulty: 'medium',
  topic: 'PostgreSQL',
  question_text: 'How would you diagnose a slow query in PostgreSQL?',
  expected_points: ['Use EXPLAIN ANALYZE', 'Check index usage'],
  follow_up_to_id: null,
  created_at: '2026-01-01T10:00:00Z',
}

const NEXT_QUESTION = { ...QUESTION, id: 'q2', position: 2, question_text: 'Second question?' }

const EVALUATION = {
  id: 'e1',
  score: 8,
  correctness: 8,
  relevance: 9,
  clarity: 7,
  completeness: 7,
  communication: 8,
  quality: 'strong',
  strengths: ['Named the right tool'],
  weaknesses: ['Did not mention statistics'],
  suggestions: ['Mention ANALYZE next time'],
  missed_points: ['Table statistics'],
  rationale: 'A solid, concrete answer.',
  generated_by: 'offline',
}

const DETAIL = {
  id: 'i1',
  title: 'Practice interview',
  status: 'in_progress',
  job_description_id: null,
  planned_question_count: 6,
  current_difficulty: 'medium',
  overall_score: null,
  summary: null,
  created_at: '2026-01-01T10:00:00Z',
  updated_at: '2026-01-01T10:00:00Z',
  turns: [],
  current_question: QUESTION,
  improvement_plan: null,
}

function renderRoom() {
  return renderWithProviders(<InterviewRoom />, {
    route: '/interviews/i1/room',
    path: '/interviews/:interviewId/room',
  })
}

describe('InterviewRoom', () => {
  beforeEach(() => {
    vi.spyOn(api.interviews, 'get').mockResolvedValue(DETAIL)
  })

  it('shows the current question with its category and difficulty', async () => {
    renderRoom()

    expect(await screen.findByText(QUESTION.question_text)).toBeInTheDocument()
    expect(screen.getByText('Technical')).toBeInTheDocument()
    expect(screen.getByText('medium')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
  })

  it('keeps the expected points hidden until the candidate asks for them', async () => {
    const user = userEvent.setup()
    renderRoom()

    await screen.findByText(QUESTION.question_text)
    // The hint would give the answer away, so it must start collapsed.
    expect(screen.getByText('Use EXPLAIN ANALYZE')).not.toBeVisible()

    await user.click(screen.getByText(/stuck\?/i))
    expect(screen.getByText('Use EXPLAIN ANALYZE')).toBeVisible()
  })

  it('will not submit an answer that is too short', async () => {
    const user = userEvent.setup()
    const stream = vi.spyOn(api.interviews, 'answerStream')
    renderRoom()

    await screen.findByText(QUESTION.question_text)
    const submit = screen.getByRole('button', { name: /submit answer/i })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/your answer/i), 'too short')
    expect(submit).toBeDisabled()
    expect(stream).not.toHaveBeenCalled()
  })

  it('submits a real answer and shows the rubric breakdown', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.interviews, 'answerStream').mockResolvedValue({
      interview_id: 'i1',
      evaluation: EVALUATION,
      next_question: NEXT_QUESTION,
      finished: false,
      progress: { answered: 1, planned_total: 6 },
      workflow_events: [],
    })

    renderRoom()
    await screen.findByText(QUESTION.question_text)

    await user.type(
      screen.getByLabelText(/your answer/i),
      'I would start with EXPLAIN ANALYZE and check whether the planner picks the index.',
    )
    await user.click(screen.getByRole('button', { name: /submit answer/i }))

    expect(await screen.findByText(/how that answer scored/i)).toBeInTheDocument()
    expect(screen.getByText('strong')).toBeInTheDocument()
    // Each rubric dimension is exposed as a meter carrying its own value.
    expect(screen.getByRole('meter', { name: 'Clarity' })).toHaveAttribute(
      'aria-valuenow',
      '7',
    )
    expect(screen.getByRole('meter', { name: 'Relevance' })).toHaveAttribute(
      'aria-valuenow',
      '9',
    )
    expect(screen.getByText('Named the right tool')).toBeInTheDocument()
    expect(screen.getByText('Mention ANALYZE next time')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next question/i })).toBeInTheDocument()
  })

  it('reports progress from the workflow while the answer is graded', async () => {
    const user = userEvent.setup()
    // Hold the call open so the transient step indicator can be observed; the
    // test releases it once it has seen the step.
    let release
    const held = new Promise((resolve) => {
      release = resolve
    })
    vi.spyOn(api.interviews, 'answerStream').mockImplementation(async (_id, _payload, options) => {
      options.onStep({ node: 'evaluate', message: 'Grading against the rubric' })
      await held
      return {
        interview_id: 'i1',
        evaluation: EVALUATION,
        next_question: NEXT_QUESTION,
        finished: false,
        progress: { answered: 1, planned_total: 6 },
        workflow_events: [],
      }
    })

    renderRoom()
    await screen.findByText(QUESTION.question_text)

    await user.type(
      screen.getByLabelText(/your answer/i),
      'A sufficiently long answer about query plans and indexes.',
    )
    await user.click(screen.getByRole('button', { name: /submit answer/i }))

    expect(await screen.findByText('Grading against the rubric')).toBeInTheDocument()

    release()
    await screen.findByText(/how that answer scored/i)
  })

  it('moves to the next question after the feedback is dismissed', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.interviews, 'answerStream').mockResolvedValue({
      interview_id: 'i1',
      evaluation: EVALUATION,
      next_question: NEXT_QUESTION,
      finished: false,
      progress: { answered: 1, planned_total: 6 },
      workflow_events: [],
    })

    renderRoom()
    await screen.findByText(QUESTION.question_text)

    await user.type(
      screen.getByLabelText(/your answer/i),
      'A sufficiently long answer about query plans and indexes.',
    )
    await user.click(screen.getByRole('button', { name: /submit answer/i }))
    await user.click(await screen.findByRole('button', { name: /next question/i }))

    expect(await screen.findByText('Second question?')).toBeInTheDocument()
    // The answer box must be cleared, or the previous answer gets resubmitted.
    expect(screen.getByLabelText(/your answer/i)).toHaveValue('')
  })

  it('offers to finish when the workflow says the interview is over', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.interviews, 'answerStream').mockResolvedValue({
      interview_id: 'i1',
      evaluation: EVALUATION,
      next_question: null,
      finished: true,
      progress: { answered: 6, planned_total: 6 },
      workflow_events: [],
    })
    const complete = vi.spyOn(api.interviews, 'complete').mockResolvedValue({})

    renderRoom()
    await screen.findByText(QUESTION.question_text)

    await user.type(
      screen.getByLabelText(/your answer/i),
      'A sufficiently long answer about query plans and indexes.',
    )
    await user.click(screen.getByRole('button', { name: /submit answer/i }))
    await user.click(await screen.findByRole('button', { name: /finish and see my plan/i }))

    await waitFor(() => expect(complete).toHaveBeenCalledWith('i1'))
  })

  it('surfaces a failed submission without losing the typed answer', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.interviews, 'answerStream').mockRejectedValue(
      new Error('The interview engine is unavailable'),
    )

    renderRoom()
    await screen.findByText(QUESTION.question_text)

    const answer = 'A sufficiently long answer about query plans and indexes.'
    await user.type(screen.getByLabelText(/your answer/i), answer)
    await user.click(screen.getByRole('button', { name: /submit answer/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The interview engine is unavailable',
    )
    // Losing what they wrote would be the worst possible response to a failure.
    expect(screen.getByLabelText(/your answer/i)).toHaveValue(answer)
  })
})
