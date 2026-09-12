import { useRef, useState } from 'react'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Loading,
  PageHeader,
  Pill,
  Textarea,
  formatDate,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

const MIN_JOB_LENGTH = 30

const PRESETS = [
  {
    label: 'Backend Engineer',
    text: 'Backend Engineer. Design and build REST APIs in Python with FastAPI, model data in PostgreSQL, and keep services fast under load. Requirements: strong Python, relational data modelling and query tuning, API design, authentication, testing discipline, Docker, and owning a service in production.',
  },
  {
    label: 'Frontend Engineer',
    text: 'Frontend Engineer. Build accessible, responsive interfaces in React. Requirements: strong JavaScript and TypeScript, React hooks and state management, CSS layout, performance profiling, testing with React Testing Library, and working closely with design on real product surfaces.',
  },
  {
    label: 'Data Analyst',
    text: 'Data Analyst. Turn product and business questions into analyses people act on. Requirements: advanced SQL including window functions, a statistics foundation, Python with pandas, dashboarding, experiment design and reading out A/B tests, and communicating findings to non-technical stakeholders.',
  },
  {
    label: 'Machine Learning Engineer',
    text: 'Machine Learning Engineer. Take models from notebook to production. Requirements: Python, PyTorch or TensorFlow, feature engineering, model evaluation and error analysis, serving and monitoring models in production, MLOps tooling, and comfort with retrieval-augmented generation and vector databases.',
  },
]

function AddJobForm({ onCreated }) {
  const fileRef = useRef(null)
  const [form, setForm] = useState({ title: '', company: '', raw_text: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function update(field) {
    return (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const job = await api.jobs.create({
        title: form.title.trim() || null,
        company: form.company.trim() || null,
        raw_text: form.raw_text.trim(),
        set_active: true,
      })
      setForm({ title: '', company: '', raw_text: '' })
      onCreated(job)
    } catch (exception) {
      setError(exception)
    } finally {
      setBusy(false)
    }
  }

  async function uploadFile(event) {
    const file = event.target.files?.[0]
    if (!file) return

    setBusy(true)
    setError(null)
    try {
      onCreated(await api.jobs.upload(file, { title: form.title.trim() || undefined }))
    } catch (exception) {
      setError(exception)
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const tooShort = form.raw_text.trim().length < MIN_JOB_LENGTH

  return (
    <Card>
      <CardHeader
        title="Add a target role"
        subtitle="Paste the posting, upload it as a file, or start from a template."
      />
      <CardBody>
        <form onSubmit={submit} className="space-y-4">
          <ErrorNote error={error} />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Job title" htmlFor="job-title" hint="Optional - we read it from the text">
              <Input
                id="job-title"
                value={form.title}
                onChange={update('title')}
                placeholder="Backend Engineer"
              />
            </Field>
            <Field label="Company" htmlFor="job-company" hint="Optional">
              <Input
                id="job-company"
                value={form.company}
                onChange={update('company')}
                placeholder="Northwind Labs"
              />
            </Field>
          </div>

          <Field
            label="Job description"
            htmlFor="job-text"
            hint={
              tooShort && form.raw_text.length > 0
                ? `At least ${MIN_JOB_LENGTH} characters`
                : 'The responsibilities and requirements sections matter most.'
            }
          >
            <Textarea
              id="job-text"
              rows={8}
              value={form.raw_text}
              onChange={update('raw_text')}
              placeholder="Paste the full job posting here..."
            />
          </Field>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-500">
              Or start from a template
            </p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() =>
                    setForm((previous) => ({
                      ...previous,
                      title: previous.title || preset.label,
                      raw_text: preset.text,
                    }))
                  }
                  className="rounded-full border border-ink-300 px-3 py-1 text-xs font-medium text-ink-600 hover:border-brand-500 hover:text-brand-700"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 pt-4">
            <label className="text-sm text-ink-600">
              <span className="mr-2">Or upload a file:</span>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain"
                onChange={uploadFile}
                disabled={busy}
                className="text-sm file:mr-2 file:rounded-lg file:border file:border-ink-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:text-ink-700 hover:file:bg-ink-50"
              />
            </label>

            <Button type="submit" loading={busy} disabled={tooShort}>
              Save role
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

export default function Jobs() {
  const { data, error, loading, reload, setData } = useAsync(() => api.jobs.list(), [])
  const [expandedId, setExpandedId] = useState(null)
  const [actionError, setActionError] = useState(null)

  async function activate(job) {
    setActionError(null)
    try {
      await api.jobs.activate(job.id)
      setData((current) =>
        current.map((item) => ({ ...item, is_active: item.id === job.id })),
      )
    } catch (exception) {
      setActionError(exception)
    }
  }

  if (loading) return <Loading label="Loading your target roles" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  return (
    <>
      <PageHeader
        title="Target roles"
        subtitle="Interview questions are matched against the role you mark as active."
      />

      <div className="space-y-6">
        <ErrorNote error={actionError} />

        <AddJobForm
          onCreated={(job) => {
            setData((current) => [job, ...current.map((item) => ({ ...item, is_active: false }))])
          }}
        />

        {data.length === 0 ? (
          <EmptyState
            title="No saved roles"
            description="Add one above. Without a target role, interviews fall back to general questions for your preferred role."
          />
        ) : (
          <Card>
            <CardHeader title={`Saved roles (${data.length})`} />
            <ul className="divide-y divide-ink-100">
              {data.map((job) => (
                <li key={job.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-ink-900">{job.title}</p>
                        {job.is_active && <Pill tone="good">Active</Pill>}
                        {job.seniority && <Pill>{job.seniority}</Pill>}
                        {job.source_document_id && <Pill tone="brand">From file</Pill>}
                      </div>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {job.company ? `${job.company} - ` : ''}
                        added {formatDate(job.created_at)}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {!job.is_active && (
                        <Button variant="secondary" size="sm" onClick={() => activate(job)}>
                          Make active
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedId(expandedId === job.id ? null : job.id)}
                        aria-expanded={expandedId === job.id}
                      >
                        {expandedId === job.id ? 'Hide' : 'View text'}
                      </Button>
                    </div>
                  </div>

                  {expandedId === job.id && (
                    <p className="mt-3 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg bg-ink-50 px-4 py-3 text-sm leading-relaxed text-ink-700">
                      {job.raw_text}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  )
}
