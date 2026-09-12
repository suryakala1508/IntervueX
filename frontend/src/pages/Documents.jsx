import { useRef, useState } from 'react'
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Input,
  Loading,
  PageHeader,
  Pill,
  Select,
  formatDateTime,
  titleCase,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

const DOC_TYPES = [
  { value: 'resume', label: 'Resume' },
  { value: 'job_description', label: 'Job description' },
  { value: 'other', label: 'Other' },
]

const DOC_TONES = { resume: 'brand', job_description: 'good', other: 'neutral' }

/**
 * Retrieval preview. This is the same search the interview workflow runs before
 * generating a question, so it is the honest way to see what the model is given.
 */
function RetrievalPreview() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function search(event) {
    event.preventDefault()
    if (query.trim().length < 2) return

    setBusy(true)
    setError(null)
    try {
      const response = await api.documents.search(query.trim())
      setResults(response.results)
    } catch (exception) {
      setError(exception)
      setResults(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="What the interviewer sees"
        subtitle="Search your indexed documents the same way the question generator does."
      />
      <CardBody className="space-y-4">
        <form onSubmit={search} className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="database indexing, system design, my payments project..."
            aria-label="Search your documents"
            className="mt-0"
          />
          <Button type="submit" loading={busy} disabled={query.trim().length < 2}>
            Search
          </Button>
        </form>

        <ErrorNote error={error} />

        {results && results.length === 0 && (
          <p className="text-sm text-ink-500">
            Nothing matched. Upload a resume, or try wording closer to what your documents say.
          </p>
        )}

        {results && results.length > 0 && (
          <ol className="space-y-3">
            {results.map((chunk) => (
              <li key={chunk.chunk_id} className="rounded-lg border border-ink-200 px-4 py-3">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <Pill tone={DOC_TONES[chunk.doc_type]}>{titleCase(chunk.doc_type)}</Pill>
                  <span className="text-xs text-ink-500">
                    page {chunk.page_number} &middot; chunk {chunk.chunk_index}
                  </span>
                  <span className="ml-auto text-xs font-medium tabular-nums text-ink-600">
                    {(chunk.score * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="text-sm leading-relaxed text-ink-700">{chunk.content}</p>
              </li>
            ))}
          </ol>
        )}
      </CardBody>
    </Card>
  )
}

export default function Documents() {
  const { data, error, loading, reload, setData } = useAsync(() => api.documents.list(), [])
  const fileRef = useRef(null)
  const [docType, setDocType] = useState('other')
  const [uploading, setUploading] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [removingId, setRemovingId] = useState(null)

  async function upload(event) {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    setActionError(null)
    try {
      const document = await api.documents.upload(file, docType)
      setData((current) => [document, ...current])
    } catch (exception) {
      setActionError(exception)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function remove(document) {
    const confirmed = window.confirm(
      `Delete ${document.filename}? Its indexed chunks are removed too, so it stops informing your interviews.`,
    )
    if (!confirmed) return

    setRemovingId(document.id)
    setActionError(null)
    try {
      await api.documents.remove(document.id)
      setData((current) => current.filter((item) => item.id !== document.id))
    } catch (exception) {
      setActionError(exception)
    } finally {
      setRemovingId(null)
    }
  }

  if (loading) return <Loading label="Loading your documents" />
  if (error) return <ErrorNote error={error} onRetry={reload} />

  const totalChunks = data.reduce((sum, document) => sum + document.chunk_count, 0)

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle={`${data.length} document${data.length === 1 ? '' : 's'} indexed into ${totalChunks} searchable chunks.`}
      />

      <div className="space-y-6">
        <ErrorNote error={actionError} />

        <Card>
          <CardHeader
            title="Upload a document"
            subtitle="PDF or plain text, up to 10 MB. Scanned PDFs need OCR first - there is no text in them to extract."
          />
          <CardBody>
            <div className="flex flex-wrap items-end gap-3">
              <label className="text-sm">
                <span className="block font-medium text-ink-700">Type</span>
                <Select
                  value={docType}
                  onChange={(event) => setDocType(event.target.value)}
                  className="w-48"
                >
                  {DOC_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </label>

              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain"
                onChange={upload}
                disabled={uploading}
                aria-label="Choose a document"
                className="flex-1 text-sm text-ink-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-700 disabled:opacity-50"
              />
            </div>
            {uploading && <p className="mt-3 text-sm text-ink-500">Extracting and embedding...</p>}
          </CardBody>
        </Card>

        {data.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description="Upload your resume on the profile page, or add supporting material here. Everything you add becomes retrievable context for your interviews."
          />
        ) : (
          <Card>
            <CardHeader title="Indexed documents" />
            <ul className="divide-y divide-ink-100">
              {data.map((document) => (
                <li
                  key={document.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium text-ink-900">
                        {document.filename}
                      </p>
                      <Pill tone={DOC_TONES[document.doc_type]}>
                        {titleCase(document.doc_type)}
                      </Pill>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {document.page_count} page{document.page_count === 1 ? '' : 's'} &middot;{' '}
                      {document.chunk_count} chunks &middot; {document.char_count.toLocaleString()}{' '}
                      characters &middot; {formatDateTime(document.created_at)}
                    </p>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => remove(document)}
                    loading={removingId === document.id}
                  >
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <RetrievalPreview />
      </div>
    </>
  )
}
