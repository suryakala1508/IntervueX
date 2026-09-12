import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  DifficultyPill,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  QualityPill,
  ScoreBadge,
  ScoreBar,
  Stat,
  StatusPill,
  formatDate,
  titleCase,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

function Transcript({ turns }) {
  if (!turns.length) return <EmptyState title="No questions were asked in this interview." />

  return (
    <ol className="space-y-4">
      {turns.map((turn, index) => {
        const { question, answer } = turn
        const evaluation = answer?.evaluation
        return (
          <li key={question.id}>
            <Card>
              <CardBody className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                      Q{index + 1}
                    </span>
                    <Pill tone="brand">{titleCase(question.category)}</Pill>
                    <DifficultyPill difficulty={question.difficulty} />
                    <Pill>{question.topic}</Pill>
                    {question.follow_up_to_id && <Pill tone="warn">Follow-up</Pill>}
                  </div>
                  {evaluation && (
                    <div className="flex items-center gap-2">
                      <QualityPill quality={evaluation.quality} />
                      <ScoreBadge score={evaluation.score} />
                    </div>
                  )}
                </div>

                <p className="font-medium leading-relaxed text-ink-900">
                  {question.question_text}
                </p>

                {answer ? (
                  <div className="rounded-lg border border-ink-200 bg-ink-50 px-4 py-3">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                      {answer.answer_text}
                    </p>
                    {answer.time_taken_seconds != null && (
                      <p className="mt-2 text-xs text-ink-400">
                        Answered in {Math.floor(answer.time_taken_seconds / 60)}m{' '}
                        {answer.time_taken_seconds % 60}s
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-sm italic text-ink-400">Not answered.</p>
                )}

                {evaluation && (
                  <div className="space-y-4 border-t border-ink-100 pt-4">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                      <ScoreBar label="Correctness" score={evaluation.correctness} />
                      <ScoreBar label="Relevance" score={evaluation.relevance} />
                      <ScoreBar label="Clarity" score={evaluation.clarity} />
                      <ScoreBar label="Completeness" score={evaluation.completeness} />
                      <ScoreBar label="Communication" score={evaluation.communication} />
                    </div>

                    {evaluation.rationale && (
                      <p className="text-sm leading-relaxed text-ink-600">{evaluation.rationale}</p>
                    )}

                    <div className="grid gap-4 sm:grid-cols-3">
                      <BulletList title="Strengths" items={evaluation.strengths} />
                      <BulletList title="Gaps" items={evaluation.weaknesses} />
                      <BulletList title="Suggestions" items={evaluation.suggestions} />
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>
          </li>
        )
      })}
    </ol>
  )
}

function BulletList({ title, items }) {
  if (!items?.length) return null
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-500">{title}</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="text-sm leading-relaxed text-ink-600">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Plan({ plan }) {
  return (
    <div className="space-y-6">
      {plan.overview && (
        <p className="text-sm leading-relaxed text-ink-700">{plan.overview}</p>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {plan.weak_topics.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink-900">Focus areas</h3>
            <div className="flex flex-wrap gap-2">
              {plan.weak_topics.map((topic) => (
                <Pill key={topic} tone="warn">
                  {topic}
                </Pill>
              ))}
            </div>
          </div>
        )}

        {plan.recommended_concepts.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink-900">Concepts to revise</h3>
            <div className="flex flex-wrap gap-2">
              {plan.recommended_concepts.map((concept) => (
                <Pill key={concept} tone="brand">
                  {concept}
                </Pill>
              ))}
            </div>
          </div>
        )}
      </div>

      {plan.daily_plan.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Day by day</h3>
          <ol className="space-y-2">
            {plan.daily_plan.map((day, index) => (
              <li
                key={day.day ?? index}
                className="flex gap-3 rounded-lg border border-ink-200 px-4 py-3"
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                  {day.day ?? index + 1}
                </span>
                <div className="min-w-0">
                  {day.focus && <p className="text-sm font-medium text-ink-900">{day.focus}</p>}
                  {day.activities?.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {day.activities.map((activity) => (
                        <li key={activity} className="text-sm text-ink-600">
                          {activity}
                        </li>
                      ))}
                    </ul>
                  )}
                  {day.estimated_minutes && (
                    <p className="mt-1 text-xs text-ink-400">
                      About {day.estimated_minutes} minutes
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {plan.coding_questions.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-900">Practice problems</h3>
          <ul className="space-y-2">
            {plan.coding_questions.map((item, index) => (
              <li
                key={item.title ?? index}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ink-200 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-ink-900">{item.title}</p>
                  {item.why && <p className="mt-0.5 text-xs text-ink-500">{item.why}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {item.topic && <Pill>{item.topic}</Pill>}
                  {item.difficulty && <DifficultyPill difficulty={item.difficulty} />}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan.project_suggestions.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink-900">Strengthen your projects</h3>
          <ul className="space-y-1.5">
            {plan.project_suggestions.map((suggestion) => (
              <li key={suggestion} className="text-sm leading-relaxed text-ink-600">
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan.resources.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink-900">Resources</h3>
          <ul className="space-y-1.5">
            {plan.resources.map((resource, index) => (
              <li key={resource.title ?? index} className="text-sm text-ink-600">
                <span className="font-medium text-ink-800">{resource.title}</span>
                {resource.kind && <Pill className="ml-2">{resource.kind}</Pill>}
                {resource.detail && <p className="mt-0.5 text-ink-500">{resource.detail}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="border-t border-ink-100 pt-3 text-xs text-ink-400">
        Generated by the {plan.generated_by} provider on {formatDate(plan.created_at)}.
      </p>
    </div>
  )
}

export default function InterviewDetail() {
  const { interviewId } = useParams()
  const { data, error, loading, reload } = useAsync(
    () => api.interviews.get(interviewId),
    [interviewId],
  )
  const [tab, setTab] = useState('transcript')
  const [completing, setCompleting] = useState(false)
  const [actionError, setActionError] = useState(null)

  async function complete() {
    setCompleting(true)
    setActionError(null)
    try {
      await api.interviews.complete(interviewId)
      await reload()
      setTab('plan')
    } catch (exception) {
      setActionError(exception)
    } finally {
      setCompleting(false)
    }
  }

  if (loading) return <Loading label="Loading the interview" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  const answered = data.turns.filter((turn) => turn.answer).length
  const tabs = [
    { value: 'transcript', label: `Transcript (${data.turns.length})` },
    { value: 'plan', label: 'Improvement plan' },
  ]

  return (
    <>
      <PageHeader title={data.title} subtitle={`Started ${formatDate(data.created_at)}`}>
        <Button as={Link} to="/interviews" variant="secondary">
          Back to interviews
        </Button>
        {data.status === 'in_progress' && (
          <>
            <Button as={Link} to={`/interviews/${data.id}/room`}>
              Resume
            </Button>
            {answered > 0 && (
              <Button variant="secondary" onClick={complete} loading={completing}>
                Finish and score
              </Button>
            )}
          </>
        )}
      </PageHeader>

      <ErrorNote error={actionError} />

      <section className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Status" value={<StatusPill status={data.status} />} />
        <Stat
          label="Overall score"
          value={data.overall_score === null ? '--' : `${data.overall_score}/10`}
        />
        <Stat label="Answered" value={`${answered} / ${data.turns.length}`} />
        <Stat label="Current difficulty" value={titleCase(data.current_difficulty)} />
      </section>

      {data.summary && (
        <Card className="mb-6">
          <CardHeader title="Summary" />
          <CardBody>
            <p className="text-sm leading-relaxed text-ink-700">{data.summary}</p>
          </CardBody>
        </Card>
      )}

      <div className="mb-4 flex gap-2 border-b border-ink-200">
        {tabs.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setTab(option.value)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === option.value
                ? 'border-brand-600 text-brand-700'
                : 'border-transparent text-ink-500 hover:text-ink-800'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {tab === 'transcript' ? (
        <Transcript turns={data.turns} />
      ) : data.improvement_plan ? (
        <Card>
          <CardBody>
            <Plan plan={data.improvement_plan} />
          </CardBody>
        </Card>
      ) : (
        <EmptyState
          title="No improvement plan yet"
          description="A plan is generated when the interview is completed. Answer at least one question, then finish the interview."
          action={
            data.status === 'in_progress' && answered > 0 ? (
              <Button onClick={complete} loading={completing}>
                Finish and generate my plan
              </Button>
            ) : null
          }
        />
      )}
    </>
  )
}
