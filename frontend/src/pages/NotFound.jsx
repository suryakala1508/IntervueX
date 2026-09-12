import { Link } from 'react-router-dom'
import { Button } from '../components/ui'

export default function NotFound() {
  return (
    <div className="grid min-h-full place-items-center px-4 py-16 text-center">
      <div className="animate-fade-in-up">
        <div
          aria-hidden
          className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-gradient-to-br from-brand-100 to-amber-100 text-4xl ring-1 ring-inset ring-brand-500/20"
        >
          🧭
        </div>
        <p className="mt-6 text-sm font-semibold uppercase tracking-wide text-brand-600">404</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-ink-900">
          Hmm, that page wandered off
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-500">
          The link may be out of date, or the item was deleted. Let’s get you back to
          practising.
        </p>
        <Button as={Link} to="/" size="lg" className="mt-8">
          Back to the dashboard
        </Button>
      </div>
    </div>
  )
}