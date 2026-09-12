import { useEffect, useRef, useState } from 'react'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Field,
  Input,
  Loading,
  PageHeader,
  Pill,
  Textarea,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

/** Repeatable list-of-objects editor (education, experience, projects, certifications). */
function RepeatableSection({ title, description, items, fields, onChange }) {
  function update(index, key, value) {
    onChange(items.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
  }

  function add() {
    onChange([...items, Object.fromEntries(fields.map((field) => [field.key, '']))])
  }

  function remove(index) {
    onChange(items.filter((_, i) => i !== index))
  }

  return (
    <Card>
      <CardHeader
        title={title}
        subtitle={description}
        action={
          <Button variant="secondary" size="sm" onClick={add} type="button">
            Add
          </Button>
        }
      />
      <CardBody className="space-y-4">
        {items.length === 0 && (
          <p className="text-sm text-ink-500">Nothing added yet.</p>
        )}

        {items.map((item, index) => (
          <div key={index} className="rounded-lg border border-ink-200 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {fields.map((field) => (
                <Field
                  key={field.key}
                  label={field.label}
                  htmlFor={`${title}-${index}-${field.key}`}
                  className={field.wide ? 'sm:col-span-2' : ''}
                >
                  {field.multiline ? (
                    <Textarea
                      id={`${title}-${index}-${field.key}`}
                      rows={2}
                      value={item[field.key] ?? ''}
                      onChange={(event) => update(index, field.key, event.target.value)}
                      placeholder={field.placeholder}
                    />
                  ) : (
                    <Input
                      id={`${title}-${index}-${field.key}`}
                      value={item[field.key] ?? ''}
                      onChange={(event) => update(index, field.key, event.target.value)}
                      placeholder={field.placeholder}
                    />
                  )}
                </Field>
              ))}
            </div>
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" type="button" onClick={() => remove(index)}>
                Remove
              </Button>
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  )
}

function SkillsEditor({ skills, onChange }) {
  const [draft, setDraft] = useState('')

  function addFromDraft() {
    // Commas let someone paste a whole list at once.
    const additions = draft
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .filter((value) => !skills.some((skill) => skill.toLowerCase() === value.toLowerCase()))

    if (additions.length) onChange([...skills, ...additions])
    setDraft('')
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {skills.length === 0 && <p className="text-sm text-ink-500">No skills yet.</p>}
        {skills.map((skill) => (
          <span
            key={skill}
            className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 py-1 pl-3 pr-1.5 text-sm text-brand-700"
          >
            {skill}
            <button
              type="button"
              onClick={() => onChange(skills.filter((value) => value !== skill))}
              className="grid h-5 w-5 place-items-center rounded-full text-brand-700 hover:bg-brand-100"
              aria-label={`Remove ${skill}`}
            >
              &times;
            </button>
          </span>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              addFromDraft()
            }
          }}
          placeholder="Python, PostgreSQL, system design"
          aria-label="Add a skill"
          className="mt-0"
        />
        <Button type="button" variant="secondary" onClick={addFromDraft}>
          Add
        </Button>
      </div>
      <p className="mt-1 text-xs text-ink-500">
        These drive question selection more than anything else on this page.
      </p>
    </div>
  )
}

function ResumeUpload({ onUploaded }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleFile(event) {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.profile.uploadResume(file)
      setResult(response)
      onUploaded(response.profile)
    } catch (exception) {
      setError(exception)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <Card>
      <CardHeader
        title="Resume"
        subtitle="A PDF or text file. We extract the text, index it for retrieval, and fill in anything you have left blank."
      />
      <CardBody className="space-y-3">
        <ErrorNote error={error} />

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain"
          onChange={handleFile}
          disabled={uploading}
          className="block w-full text-sm text-ink-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-700 disabled:opacity-50"
          aria-label="Upload your resume"
        />

        {uploading && <p className="text-sm text-ink-500">Extracting and indexing...</p>}

        {result && (
          <div className="rounded-lg border border-good-500/30 bg-good-500/10 px-4 py-3 text-sm text-ink-700">
            <p className="font-medium text-good-600">
              Indexed {result.document.filename}
            </p>
            <p className="mt-0.5 text-ink-600">
              {result.document.page_count} page{result.document.page_count === 1 ? '' : 's'},{' '}
              {result.document.chunk_count} searchable chunks.
              {result.extracted_fields?.parsed === false &&
                ' Automatic parsing was unavailable, so fill in the fields below yourself.'}
            </p>
          </div>
        )}

        <p className="text-xs text-ink-500">
          Your own entries are never overwritten - parsing only fills gaps and adds new skills.
        </p>
      </CardBody>
    </Card>
  )
}

const EMPTY = {
  headline: '',
  location: '',
  years_of_experience: '',
  preferred_role: '',
  target_company: '',
  summary: '',
  skills: [],
  education: [],
  experience: [],
  projects: [],
  certifications: [],
}

export default function Profile() {
  const { data, error, loading, reload } = useAsync(() => api.profile.get(), [])
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!data) return
    setForm({
      ...EMPTY,
      ...data,
      // Nulls from the API would make the inputs uncontrolled.
      headline: data.headline ?? '',
      location: data.location ?? '',
      years_of_experience: data.years_of_experience ?? '',
      preferred_role: data.preferred_role ?? '',
      target_company: data.target_company ?? '',
      summary: data.summary ?? '',
    })
  }, [data])

  function set(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }))
    setSaved(false)
  }

  function update(field) {
    return (event) => set(field, event.target.value)
  }

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      await api.profile.update({
        headline: form.headline || null,
        location: form.location || null,
        years_of_experience: form.years_of_experience === '' ? null : Number(form.years_of_experience),
        preferred_role: form.preferred_role || null,
        target_company: form.target_company || null,
        summary: form.summary || null,
        skills: form.skills,
        education: form.education,
        experience: form.experience,
        projects: form.projects,
        certifications: form.certifications,
      })
      setSaved(true)
    } catch (exception) {
      setSaveError(exception)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading label="Loading your profile" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  return (
    <form onSubmit={save}>
      <PageHeader
        title="Your profile"
        subtitle="Everything here feeds the questions you get asked. The more specific, the better the interview."
      >
        {saved && <Pill tone="good">Saved</Pill>}
        <Button type="submit" loading={saving}>
          Save profile
        </Button>
      </PageHeader>

      <div className="space-y-6">
        <ErrorNote error={saveError} />

        <ResumeUpload
          onUploaded={(profile) => {
            setForm({
              ...EMPTY,
              ...profile,
              headline: profile.headline ?? '',
              location: profile.location ?? '',
              years_of_experience: profile.years_of_experience ?? '',
              preferred_role: profile.preferred_role ?? '',
              target_company: profile.target_company ?? '',
              summary: profile.summary ?? '',
            })
          }}
        />

        <Card>
          <CardHeader title="Basics" />
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Headline" htmlFor="headline" className="sm:col-span-2">
              <Input
                id="headline"
                value={form.headline}
                onChange={update('headline')}
                placeholder="Backend engineer building Python services"
              />
            </Field>

            <Field label="Location" htmlFor="location">
              <Input id="location" value={form.location} onChange={update('location')} />
            </Field>

            <Field label="Years of experience" htmlFor="years_of_experience">
              <Input
                id="years_of_experience"
                type="number"
                min={0}
                max={60}
                step={0.5}
                value={form.years_of_experience}
                onChange={update('years_of_experience')}
              />
            </Field>

            <Field
              label="Preferred role"
              htmlFor="preferred_role"
              hint="Used when no target job is selected"
            >
              <Input
                id="preferred_role"
                value={form.preferred_role}
                onChange={update('preferred_role')}
                placeholder="Backend Engineer"
              />
            </Field>

            <Field label="Target company" htmlFor="target_company">
              <Input
                id="target_company"
                value={form.target_company}
                onChange={update('target_company')}
              />
            </Field>

            <Field label="Summary" htmlFor="summary" className="sm:col-span-2">
              <Textarea
                id="summary"
                rows={3}
                value={form.summary}
                onChange={update('summary')}
                placeholder="Two or three sentences on what you build and what you are aiming for."
              />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Skills" subtitle="What you want to be questioned on" />
          <CardBody>
            <SkillsEditor skills={form.skills} onChange={(skills) => set('skills', skills)} />
          </CardBody>
        </Card>

        <RepeatableSection
          title="Experience"
          description="Roles you have held"
          items={form.experience}
          onChange={(value) => set('experience', value)}
          fields={[
            { key: 'title', label: 'Title', placeholder: 'Backend Engineer' },
            { key: 'company', label: 'Company' },
            { key: 'period', label: 'Period', placeholder: '2022 - present' },
            { key: 'description', label: 'What you did', wide: true, multiline: true },
          ]}
        />

        <RepeatableSection
          title="Projects"
          description="Projects get their own interview questions, so describe what you actually built"
          items={form.projects}
          onChange={(value) => set('projects', value)}
          fields={[
            { key: 'name', label: 'Name' },
            { key: 'tech', label: 'Stack', placeholder: 'FastAPI, PostgreSQL' },
            { key: 'description', label: 'Description', wide: true, multiline: true },
          ]}
        />

        <RepeatableSection
          title="Education"
          items={form.education}
          onChange={(value) => set('education', value)}
          fields={[
            { key: 'degree', label: 'Degree' },
            { key: 'institution', label: 'Institution' },
            { key: 'year', label: 'Year' },
            { key: 'details', label: 'Details', wide: true },
          ]}
        />

        <RepeatableSection
          title="Certifications"
          items={form.certifications}
          onChange={(value) => set('certifications', value)}
          fields={[
            { key: 'name', label: 'Name' },
            { key: 'issuer', label: 'Issuer' },
            { key: 'year', label: 'Year' },
          ]}
        />

        <div className="flex items-center justify-end gap-3 pb-4">
          {saved && <Pill tone="good">Saved</Pill>}
          <Button type="submit" loading={saving}>
            Save profile
          </Button>
        </div>
      </div>
    </form>
  )
}
