import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Card,
  CardBody,
  DifficultyPill,
  ErrorNote,
  Loading,
  Pill,
  QualityPill,
  ScoreBar,
  Spinner,
  Textarea,
  titleCase,
} from '../components/ui'
import { api } from '../lib/api'

const MIN_ANSWER_LENGTH = 10

function useElapsedSeconds(resetKey) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    setSeconds(0)
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000)
    return () => clearInterval(timer)
  }, [resetKey])
  return seconds
}

function formatClock(totalSeconds) {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

/** The evaluation panel shown between questions. */
function Feedback({ evaluation, onContinue, continueLabel, busy }) {
  return (
    <Card className="animate-fade-in-up border-brand-300">
      <CardBody className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-bold tracking-tight text-ink-900">
            How that answer scored
          </h2>
          <div className="flex items-center gap-2">
            <QualityPill quality={evaluation.quality} />
            <span className="inline-flex items-baseline gap-0.5 rounded-full bg-brand-100 px-3 py-1 text-2xl font-bold tabular-nums text-brand-700 ring-1 ring-inset ring-brand-500/25">
              {evaluation.score}
              <span className="text-sm font-semibold opacity-70">/10</span>
            </span>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <ScoreBar label="Correctness" score={evaluation.correctness} />
          <ScoreBar label="Relevance" score={evaluation.relevance} />
          <ScoreBar label="Clarity" score={evaluation.clarity} />
          <ScoreBar label="Completeness" score={evaluation.completeness} />
          <ScoreBar label="Communication" score={evaluation.communication} />
        </div>

        {evaluation.rationale && (
          <p className="text-sm leading-relaxed text-ink-700">{evaluation.rationale}</p>
        )}

        <div className="grid gap-5 sm:grid-cols-3">
          <FeedbackList title="Strengths" items={evaluation.strengths} tone="good" />
          <FeedbackList title="Gaps" items={evaluation.weaknesses} tone="warn" />
          <FeedbackList title="Do this next time" items={evaluation.suggestions} tone="brand" />
        </div>

        {evaluation.missed_points?.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-500">
              Points an interviewer would have wanted
            </p>
            <div className="flex flex-wrap gap-2">
              {evaluation.missed_points.map((point) => (
                <Pill key={point} tone="bad">
                  {point}
                </Pill>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end border-t border-ink-100 pt-4">
          <Button onClick={onContinue} loading={busy} size="lg">
            {continueLabel}
          </Button>
        </div>
      </CardBody>
    </Card>
  )
}

const LIST_DOT = { good: 'bg-good-500', warn: 'bg-warn-500', brand: 'bg-brand-500' }

function FeedbackList({ title, items, tone }) {
  if (!items?.length) return null
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-500">{title}</p>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-ink-700">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${LIST_DOT[tone]}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function InterviewRoom() {
  const { interviewId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Starting the interview already returned the first question; reuse it rather
  // than refetching, and fall back to the API on a direct visit or a reload.
  const started = location.state?.started

  const [interview, setInterview] = useState(started?.interview ?? null)
  const [question, setQuestion] = useState(started?.first_question ?? null)
  const [answer, setAnswer] = useState('')
  const [evaluation, setEvaluation] = useState(null)
  const [progress, setProgress] = useState(null)
  const [finished, setFinished] = useState(false)
  const [step, setStep] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(!started)

  const elapsed = useElapsedSeconds(question?.id)
  const answerRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const detail = await api.interviews.get(interviewId)
      setInterview(detail)
      setQuestion(detail.current_question)
      setFinished(detail.status !== 'in_progress' || !detail.current_question)
      // Resuming mid-interview: recover the count from the transcript so the
      // progress bar does not restart at zero.
      setProgress({
        answered: detail.turns.filter((turn) => turn.answer).length,
        planned_total: detail.planned_question_count,
      })
      setError(null)
    } catch (exception) {
      setError(exception)
    } finally {
      setLoading(false)
    }
  }, [interviewId])

  useEffect(() => {
    if (!started) load()
  }, [started, load])

  useEffect(() => {
    if (question && !evaluation) answerRef.current?.focus()
  }, [question, evaluation])

  // A half-written answer is worth guarding; a finished interview is not.
  useEffect(() => {
    function warn(event) {
      if (!busy && !answer.trim()) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [answer, busy])

  const tooShort = answer.trim().length < MIN_ANSWER_LENGTH

  async function submit(event) {
    event.preventDefault()
    if (tooShort || busy) return

    setBusy(true)
    setError(null)
    setStep('Recording your answer')
    try {
      const result = await api.interviews.answerStream(
        interviewId,
        {
          question_id: question.id,
          answer_text: answer.trim(),
          time_taken_seconds: elapsed,
        },
        { onStep: (data) => setStep(data.message) },
      )
      setEvaluation(result.evaluation)
      setProgress(result.progress)
      setFinished(result.finished)
      // Held until "Next question" is pressed, so the feedback is read first.
      setQuestion((current) => result.next_question ?? current)
      setAnswer('')
    } catch (exception) {
      setError(exception)
    } finally {
      setBusy(false)
      setStep(null)
    }
  }

  async function handleContinue() {
    if (!finished) {
      setEvaluation(null)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.interviews.complete(interviewId)
      navigate(`/interviews/${interviewId}`, { replace: true })
    } catch (exception) {
      setError(exception)
      setBusy(false)
    }
  }

  async function handleExit() {
    const confirmed = window.confirm(
      'Leave this interview? You can come back and finish it later from your interview list.',
    )
    if (confirmed) navigate('/interviews')
  }

  const answered = progress?.answered ?? 0
  const planned = progress?.planned_total ?? interview?.planned_question_count ?? 0
  const pct = useMemo(
    () => (planned ? Math.min(100, Math.round((answered / planned) * 100)) : 0),
    [answered, planned],
  )

  if (loading) return <Loading label="Loading the interview" />

  if (!question && !evaluation) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <ErrorNote error={error} />
        <p className="text-sm text-ink-600">
          This interview has no question waiting. It may already be finished.
        </p>
        <Button className="mt-4" onClick={() => navigate(`/interviews/${interviewId}`)}>
          View the transcript
        </Button>
      </div>
    )
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 border-b border-ink-200/60 bg-white/80 backdrop-blur-md">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink-900">
                {interview?.title ?? 'Interview'}
              </p>
              <p className="text-xs text-ink-500">
                Question {answered + 1}
                {planned ? ` of about ${planned}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="tabular-nums text-sm text-ink-500" aria-label="Time on this question">
                {formatClock(elapsed)}
              </span>
              <Button variant="ghost" size="sm" onClick={handleExit} disabled={busy}>
                Save and exit
              </Button>
            </div>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-amber-500 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 space-y-5 px-4 py-8">
        <ErrorNote error={error} />

        {evaluation ? (
          <Feedback
            evaluation={evaluation}
            busy={busy}
            onContinue={handleContinue}
            continueLabel={finished ? 'Finish and see my plan' : 'Next question'}
          />
        ) : (
          <>
            <Card>
              <CardBody className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill tone="brand">{titleCase(question.category)}</Pill>
                  <DifficultyPill difficulty={question.difficulty} />
                  <Pill>{question.topic}</Pill>
                  {question.follow_up_to_id && <Pill tone="warn">Follow-up</Pill>}
                </div>

                <p className="text-lg leading-relaxed text-ink-900">{question.question_text}</p>

                {question.expected_points?.length > 0 && (
                  <details className="rounded-lg border border-ink-200 bg-ink-50 px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium text-ink-600">
                      Stuck? Reveal what a strong answer covers
                    </summary>
                    <ul className="mt-2 space-y-1">
                      {question.expected_points.map((point) => (
                        <li key={point} className="flex gap-2 text-sm text-ink-600">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-300" />
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </CardBody>
            </Card>

            <form onSubmit={submit}>
              <Card>
                <CardBody className="space-y-3">
                  <label htmlFor="answer" className="text-sm font-medium text-ink-700">
                    Your answer
                  </label>
                  <Textarea
                    id="answer"
                    ref={answerRef}
                    rows={10}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    disabled={busy}
                    placeholder="Answer as you would out loud. Say what you would do, why, and what you would check."
                    className="mt-0 resize-y"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-ink-500">
                      {answer.trim().split(/\s+/).filter(Boolean).length} words
                      {tooShort && answer.length > 0 && ' - keep going'}
                    </p>

                    <div className="flex items-center gap-3">
                      {busy && step && (
                        <span className="flex items-center gap-2 text-xs text-ink-500">
                          <Spinner className="h-3.5 w-3.5" />
                          {step}
                        </span>
                      )}
                      <Button type="submit" size="lg" disabled={tooShort} loading={busy}>
                        Submit answer
                      </Button>
                    </div>
                  </div>
                </CardBody>
              </Card>
            </form>
          </>
        )}
      </main>
    </div>
  )
}
