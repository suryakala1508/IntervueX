import { useState } from 'react'
import { Link } from 'react-router-dom'
import StartInterviewDialog from '../components/StartInterviewDialog'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  ScoreBadge,
  StatusPill,
  formatDate,
  titleCase,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'abandoned', label: 'Abandoned' },
]

export default function Interviews() {
  const { data, error, loading, reload, setData } = useAsync(() => api.interviews.list(), [])
  const [filter, setFilter] = useState('all')
  const [removingId, setRemovingId] = useState(null)
  const [actionError, setActionError] = useState(null)

  async function remove(interview) {
    const confirmed = window.confirm(
      `Delete "${interview.title}"? Its questions, answers, and plan go with it. This cannot be undone.`,
    )
    if (!confirmed) return

    setRemovingId(interview.id)
    setActionError(null)
    try {
      await api.interviews.remove(interview.id)
      setData((current) => current.filter((item) => item.id !== interview.id))
    } catch (exception) {
      setActionError(exception)
    } finally {
      setRemovingId(null)
    }
  }

  if (loading) return <Loading label="Loading your interviews" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  const interviews = filter === 'all' ? data : data.filter((item) => item.status === filter)

  return (
    <>
      <PageHeader title="Interviews" subtitle="Everything you have practised, newest first.">
        <StartInterviewDialog />
      </PageHeader>

      <ErrorNote error={actionError} />

      {data.length === 0 ? (
        <EmptyState
          title="Nothing here yet"
          description="Start an interview and it will show up here with its transcript, scores, and improvement plan."
          action={<StartInterviewDialog />}
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {FILTERS.map((option) => {
              const count =
                option.value === 'all'
                  ? data.length
                  : data.filter((item) => item.status === option.value).length
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFilter(option.value)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    filter === option.value
                      ? 'bg-brand-600 text-white'
                      : 'bg-white text-ink-600 ring-1 ring-ink-200 hover:bg-ink-50'
                  }`}
                >
                  {option.label}
                  <span className="ml-1.5 opacity-60">{count}</span>
                </button>
              )
            })}
          </div>

          {interviews.length === 0 ? (
            <EmptyState title={`No ${titleCase(filter).toLowerCase()} interviews`} />
          ) : (
            <Card>
              <ul className="divide-y divide-ink-100">
                {interviews.map((interview) => (
                  <li
                    key={interview.id}
                    className="flex flex-wrap items-center justify-between gap-4 px-5 py-4"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/interviews/${interview.id}`}
                        className="text-sm font-medium text-ink-900 hover:text-brand-600"
                      >
                        {interview.title}
                      </Link>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {formatDate(interview.created_at)} &middot; {interview.planned_question_count}{' '}
                        questions planned &middot; difficulty {interview.current_difficulty}
                      </p>
                      {interview.summary && (
                        <p className="mt-1 line-clamp-2 text-sm text-ink-600">{interview.summary}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusPill status={interview.status} />
                      <ScoreBadge score={interview.overall_score} />

                      {interview.status === 'in_progress' ? (
                        <Button as={Link} to={`/interviews/${interview.id}/room`} size="sm">
                          Resume
                        </Button>
                      ) : (
                        <Button
                          as={Link}
                          to={`/interviews/${interview.id}`}
                          variant="secondary"
                          size="sm"
                        >
                          Review
                        </Button>
                      )}

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => remove(interview)}
                        loading={removingId === interview.id}
                        aria-label={`Delete ${interview.title}`}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </>
  )
}
