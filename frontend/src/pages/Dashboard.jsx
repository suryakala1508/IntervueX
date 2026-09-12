import { Suspense, lazy } from 'react'
import { Link } from 'react-router-dom'
import Hero from '../components/Hero'
import PrimaryActionCard from '../components/PrimaryActionCard'
import SetupGuide from '../components/SetupGuide'
import StartInterviewDialog from '../components/StartInterviewDialog'
import {
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Loading,
  Pill,
  ScoreBadge,
  ScoreBar,
  Stat,
  StatusPill,
  formatDate,
  titleCase,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

const RUBRIC_LABELS = {
  correctness: 'Correctness',
  relevance: 'Relevance',
  clarity: 'Clarity',
  completeness: 'Completeness',
  communication: 'Communication',
}

const ProgressChart = lazy(() => import('../components/ProgressChart'))

function TopicList({ topics, emptyLabel }) {
  if (!topics.length) return <p className="text-sm text-ink-500">{emptyLabel}</p>
  return (
    <ul className="space-y-3">
      {topics.map((topic) => (
        <li key={topic.topic}>
          <ScoreBar label={topic.topic} score={topic.average_score} />
          <p className="mt-1 text-xs text-ink-400">
            {topic.answer_count} answer{topic.answer_count === 1 ? '' : 's'}
          </p>
        </li>
      ))}
    </ul>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(() => api.dashboard.get(), [])

  if (loading) return <Loading label="Loading your dashboard" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  const hasHistory = data.total_interviews > 0
  const firstName = user?.full_name?.split(' ')[0] ?? 'there'

  return (
    <>
      <Hero
        eyebrow={`Welcome back, ${firstName}`}
        title={hasHistory ? 'Keep the momentum going.' : 'Practice interviews. Build confidence.'}
        subtitle={
          hasHistory
            ? 'Here is where you stand and what to sharpen next.'
            : 'Your skills, your target role, and a coach that adapts to how you answer.'
        }
      />

      {!hasHistory ? (
        <div className="mt-10 space-y-12">
          <PrimaryActionCard
            icon="🌱"
            title="No interviews yet — let’s get your first one started!"
            description="Add your skills on the profile page and save a target job description; the questions are generated from both, so a few minutes there pays off immediately."
            action={<StartInterviewDialog label="Set up and start" size="lg" />}
          />
          <SetupGuide />
        </div>
      ) : (
        <div className="mt-10 space-y-6">
          <PrimaryActionCard
            icon="🎙️"
            title="Ready for your next round?"
            description="Answer a question to raise the difficulty; stumble and it steps back to fundamentals. Each answer is scored against the same five-point rubric, so your progress stays comparable."
            action={<StartInterviewDialog label="Start a practice interview" size="lg" />}
          />

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Interviews"
              value={data.total_interviews}
              hint={`${data.completed_interviews} completed`}
            />
            <Stat
              label="Average score"
              value={data.average_score === null ? '--' : `${data.average_score}/10`}
              hint={`across ${data.total_answers} answers`}
            />
            <Stat
              label="Best score"
              value={data.best_score === null ? '--' : `${data.best_score}/10`}
            />
            <Stat label="Answers graded" value={data.total_answers} />
          </section>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Progress over time"
                subtitle="Overall score of each completed interview"
              />
              <CardBody>
                {data.progress.length > 1 ? (
                  <Suspense fallback={<div className="h-[220px]" />}>
                    <ProgressChart points={data.progress} />
                  </Suspense>
                ) : (
                  <p className="py-10 text-center text-sm text-ink-500">
                    Complete a second interview to see a trend line here.
                  </p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Rubric averages" subtitle="Where the marks come from" />
              <CardBody>
                {data.rubric_averages ? (
                  <div className="space-y-4">
                    {Object.entries(RUBRIC_LABELS).map(([key, label]) => (
                      <ScoreBar key={key} label={label} score={data.rubric_averages[key]} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-ink-500">Answer a question to populate this.</p>
                )}
              </CardBody>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Work on these" subtitle="Topics scoring below 6.5" />
              <CardBody>
                <TopicList
                  topics={data.weak_topics}
                  emptyLabel="Nothing below the threshold - keep going to find your edges."
                />
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Your strengths" subtitle="Highest scoring topics" />
              <CardBody>
                <TopicList topics={data.strongest_topics} emptyLabel="No graded topics yet." />
              </CardBody>
            </Card>
          </div>

          {data.latest_plan && (
            <Card>
              <CardHeader
                title="Latest improvement plan"
                subtitle={`Generated ${formatDate(data.latest_plan.created_at)}`}
                action={
                  <Link
                    to={`/interviews/${data.latest_plan.interview_id}`}
                    className="text-sm font-semibold text-brand-600 hover:text-brand-700"
                  >
                    Open full plan
                  </Link>
                }
              />
              <CardBody className="space-y-4">
                {data.latest_plan.overview && (
                  <p className="text-sm leading-relaxed text-ink-700">
                    {data.latest_plan.overview}
                  </p>
                )}
                {data.latest_plan.recommended_concepts.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                      Concepts to revise
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {data.latest_plan.recommended_concepts.slice(0, 10).map((concept) => (
                        <Pill key={concept} tone="brand">
                          {concept}
                        </Pill>
                      ))}
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader
              title="Recent interviews"
              action={
                <Link to="/interviews" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
                  View all
                </Link>
              }
            />
            <ul className="divide-y divide-ink-100">
              {data.recent_interviews.map((interview) => (
                <li key={interview.id}>
                  <Link
                    to={`/interviews/${interview.id}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 transition-colors duration-300 hover:bg-cream-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-900">
                        {interview.title}
                      </p>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {formatDate(interview.created_at)} &middot;{' '}
                        {titleCase(interview.current_difficulty)}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusPill status={interview.status} />
                      <ScoreBadge score={interview.overall_score} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </>
  )
}