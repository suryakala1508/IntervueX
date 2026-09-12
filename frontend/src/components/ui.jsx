/** Shared presentational primitives, so pages stay about behaviour. */

import { Link } from 'react-router-dom'
import FeedbackBadge from './FeedbackBadge'
export { default as EmptyState } from './EmptyState'

/* -- layout ---------------------------------------------------------------- */

export function Card({ children, className = '', ...rest }) {
  return (
    <div
      className={`rounded-[20px] border border-ink-200/70 bg-white shadow-soft transition-shadow duration-300 ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-6 py-5">
      <div>
        <h2 className="text-lg font-semibold text-ink-900">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={`px-6 py-5 ${className}`}>{children}</div>
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 animate-fade-in-up">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </header>
  )
}

/* -- controls -------------------------------------------------------------- */

const BUTTON_VARIANTS = {
  primary:
    'bg-gradient-to-r from-brand-500 to-amber-500 text-white shadow-md shadow-brand-500/30 hover:from-brand-600 hover:to-amber-600 hover:shadow-lg hover:shadow-brand-500/40 disabled:from-ink-300 disabled:to-ink-300 disabled:shadow-none',
  secondary:
    'bg-white text-ink-700 border border-ink-200 hover:bg-cream-50 hover:border-ink-300 disabled:text-ink-400',
  ghost: 'text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 disabled:text-ink-300',
  danger: 'bg-bad-500 text-white hover:bg-bad-600 disabled:opacity-50',
}

const BUTTON_SIZES = {
  sm: 'px-3.5 py-1.5 text-xs',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-7 py-3 text-base',
}

export function Button({
  variant = 'primary',
  size = 'md',
  as: Component = 'button',
  className = '',
  loading = false,
  disabled,
  children,
  ...rest
}) {
  return (
    <Component
      className={`inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 disabled:cursor-not-allowed disabled:hover:translate-y-0 ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </Component>
  )
}

export function LinkButton({ to, ...rest }) {
  return <Button as={Link} to={to} {...rest} />
}

export function Field({ label, hint, error, htmlFor, children, className = '' }) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink-700">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
      {error && (
        <p className="mt-1 text-xs text-bad-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

const CONTROL =
  'mt-1 w-full rounded-[16px] border border-ink-200 bg-white px-4 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 transition-all duration-300 focus:border-brand-500 focus:ring-4 focus:ring-brand-100 disabled:bg-ink-50'

export function Input({ className = '', ...rest }) {
  return <input className={`${CONTROL} ${className}`} {...rest} />
}

export function Textarea({ className = '', ...rest }) {
  return <textarea className={`${CONTROL} ${className}`} {...rest} />
}

export function Select({ className = '', children, ...rest }) {
  return (
    <select className={`${CONTROL} ${className}`} {...rest}>
      {children}
    </select>
  )
}

/* -- feedback -------------------------------------------------------------- */

export function Spinner({ className = 'h-5 w-5' }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
        fill="none"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  )
}

export function Loading({ label = 'Loading' }) {
  return (
    <div
      className="flex items-center justify-center gap-3 py-16 text-ink-500 animate-fade-in-up"
      role="status"
    >
      <Spinner />
      <span className="text-sm">{label}...</span>
    </div>
  )
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  const message = typeof error === 'string' ? error : error.message
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-bad-500/30 bg-bad-500/10 px-4 py-3 text-sm text-bad-700"
    >
      <span>{message}</span>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

/* -- data display ---------------------------------------------------------- */

/** Colour by score band: red below 5, amber to 7, green above. */
export function scoreTone(score) {
  if (score === null || score === undefined) return 'ink'
  if (score >= 7.5) return 'good'
  if (score >= 5) return 'warn'
  return 'bad'
}

const TONE_CHIP = {
  good: 'bg-good-500/15 text-good-700 ring-good-500/30',
  warn: 'bg-warn-500/20 text-warn-700 ring-warn-500/30',
  bad: 'bg-bad-500/15 text-bad-700 ring-bad-500/30',
  ink: 'bg-ink-100 text-ink-500 ring-ink-300/40',
}

const TONE_BAR = {
  good: 'bg-gradient-to-r from-good-500 to-good-600',
  warn: 'bg-gradient-to-r from-warn-500 to-warn-600',
  bad: 'bg-gradient-to-r from-bad-500 to-bad-600',
  ink: 'bg-ink-300',
}

export function ScoreBadge({ score, outOf = 10, className = '' }) {
  const tone = scoreTone(score)
  return (
    <span
      className={`inline-flex items-baseline gap-0.5 rounded-full px-2 py-0.5 text-sm font-semibold tabular-nums ring-1 ring-inset ${TONE_CHIP[tone]} ${className}`}
    >
      {score === null || score === undefined ? '--' : score}
      <span className="text-xs opacity-70">/{outOf}</span>
    </span>
  )
}

export function ScoreBar({ label, score, outOf = 10 }) {
  const pct = score === null || score === undefined ? 0 : (score / outOf) * 100
  const tone = scoreTone(score)
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink-600">{label}</span>
        <ScoreBadge score={score} outOf={outOf} />
      </div>
      <div
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-ink-100"
        role="meter"
        aria-valuenow={score ?? 0}
        aria-valuemin={0}
        aria-valuemax={outOf}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${TONE_BAR[tone]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function Stat({ label, value, hint }) {
  return (
    <div className="rounded-[20px] border border-ink-200/70 bg-white px-6 py-5 shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">{label}</p>
      <p className="mt-1.5 text-3xl font-bold tabular-nums text-ink-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

const PILL_TONES = {
  neutral: 'neutral',
  brand: 'brand',
  good: 'good',
  warn: 'warn',
  bad: 'bad',
}

export function Pill({ tone = 'neutral', children, className = '' }) {
  return (
    <FeedbackBadge tone={PILL_TONES[tone] ?? 'neutral'} className={className}>
      {children}
    </FeedbackBadge>
  )
}

const STATUS_TONES = {
  completed: 'good',
  in_progress: 'brand',
  abandoned: 'neutral',
}

export function StatusPill({ status }) {
  return (
    <Pill tone={STATUS_TONES[status] ?? 'neutral'}>{String(status).replace('_', ' ')}</Pill>
  )
}

const QUALITY_TONES = {
  strong: 'good',
  adequate: 'brand',
  weak: 'warn',
  incomplete: 'bad',
}

export function QualityPill({ quality }) {
  return <Pill tone={QUALITY_TONES[quality] ?? 'neutral'}>{quality}</Pill>
}

const DIFFICULTY_TONES = { easy: 'good', medium: 'warn', hard: 'bad' }

export function DifficultyPill({ difficulty }) {
  return <Pill tone={DIFFICULTY_TONES[difficulty] ?? 'neutral'}>{difficulty}</Pill>
}

/* -- formatting ------------------------------------------------------------ */

export function formatDate(value) {
  if (!value) return '--'
  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDateTime(value) {
  if (!value) return '--'
  return new Date(value).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function titleCase(value) {
  return String(value ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}