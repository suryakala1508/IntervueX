import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { Button, ErrorNote, Field, Input, Select } from './ui'

const DIFFICULTIES = [
  { value: 'easy', label: 'Easy - warm up' },
  { value: 'medium', label: 'Medium - realistic' },
  { value: 'hard', label: 'Hard - stretch me' },
]

/**
 * Button plus modal for configuring and starting an interview.
 *
 * Starting is the slow call in the product (retrieval, then generation), so the
 * dialog stays open with an explicit busy state rather than navigating early to
 * a screen with nothing on it.
 */
export default function StartInterviewDialog({
  label = 'Start an interview',
  variant = 'primary',
  size = 'md',
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    title: '',
    job_description_id: '',
    question_count: 6,
    starting_difficulty: 'medium',
  })
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const dialogRef = useRef(null)

  const { data: jobs } = useAsync(() => (open ? api.jobs.list() : Promise.resolve([])), [open])

  // Preselect whichever role the candidate marked active.
  useEffect(() => {
    if (!jobs?.length) return
    const active = jobs.find((job) => job.is_active) ?? jobs[0]
    setForm((previous) =>
      previous.job_description_id ? previous : { ...previous, job_description_id: active.id },
    )
  }, [jobs])

  useEffect(() => {
    if (!open) return
    function onKeyDown(event) {
      if (event.key === 'Escape' && !starting) setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    dialogRef.current?.focus()
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, starting])

  useEffect(() => {
    if (!open) return undefined
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = originalOverflow
    }
  }, [open])

  function update(field) {
    return (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }))
  }

  async function handleStart(event) {
    event.preventDefault()
    setError(null)
    setStarting(true)
    try {
      const result = await api.interviews.start({
        title: form.title.trim() || null,
        job_description_id: form.job_description_id || null,
        question_count: Number(form.question_count),
        starting_difficulty: form.starting_difficulty,
      })
      navigate(`/interviews/${result.interview.id}/room`, { state: { started: result } })
    } catch (exception) {
      setError(exception)
      setStarting(false)
    }
  }

  return (
    <>
      <Button variant={variant} size={size} onClick={() => setOpen(true)}>
        {label}
      </Button>

      {open &&
        createPortal(
          <div
            className="pointer-events-auto fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/50 p-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="start-interview-title"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget && !starting) setOpen(false)
            }}
          >
            <div
              ref={dialogRef}
              tabIndex={-1}
              className="pointer-events-auto my-auto w-full max-w-md animate-fade-in-up rounded-[24px] border border-ink-200/70 bg-white p-7 opacity-100 shadow-lift"
            >
              <h2
                id="start-interview-title"
                className="text-2xl font-bold tracking-tight text-ink-900"
              >
                Start an interview
              </h2>
              <p className="mt-1 text-sm text-ink-500">
                Questions are drawn from your profile and the role you pick.
              </p>

              <form onSubmit={handleStart} className="mt-5 space-y-4">
                <ErrorNote error={error} />

                <Field
                  label="Target role"
                  htmlFor="job_description_id"
                  hint={
                    jobs?.length
                      ? undefined
                      : 'No saved roles yet - the interview will use general questions.'
                  }
                >
                  <Select
                    id="job_description_id"
                    value={form.job_description_id}
                    onChange={update('job_description_id')}
                  >
                    <option value="">General practice (no specific role)</option>
                    {(jobs ?? []).map((job) => (
                      <option key={job.id} value={job.id}>
                        {job.title}
                        {job.company ? ` - ${job.company}` : ''}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Field label="Name this session" htmlFor="title" hint="Optional">
                  <Input
                    id="title"
                    value={form.title}
                    onChange={update('title')}
                    placeholder="Northwind Labs - round 1"
                  />
                </Field>

                <div className="grid grid-cols-2 gap-4">
                  <Field label="Questions" htmlFor="question_count">
                    <Input
                      id="question_count"
                      type="number"
                      min={3}
                      max={20}
                      value={form.question_count}
                      onChange={update('question_count')}
                    />
                  </Field>

                  <Field label="Starting difficulty" htmlFor="starting_difficulty">
                    <Select
                      id="starting_difficulty"
                      value={form.starting_difficulty}
                      onChange={update('starting_difficulty')}
                    >
                      {DIFFICULTIES.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setOpen(false)}
                    disabled={starting}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" loading={starting}>
                    {starting ? 'Preparing questions' : 'Begin'}
                  </Button>
                </div>
              </form>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
