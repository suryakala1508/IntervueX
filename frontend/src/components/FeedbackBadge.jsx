/** Soft colour-coded chip for scores, quality, status, etc. */

export const FEEDBACK_TONES = {
  good: 'bg-good-500/15 text-good-700 ring-good-500/30',
  warn: 'bg-warn-500/20 text-warn-700 ring-warn-500/30',
  bad: 'bg-bad-500/15 text-bad-700 ring-bad-500/30',
  brand: 'bg-brand-100 text-brand-700 ring-brand-500/25',
  neutral: 'bg-ink-100 text-ink-600 ring-ink-300/50',
}

const DOT_TONES = {
  good: 'bg-good-500',
  warn: 'bg-warn-500',
  bad: 'bg-bad-500',
  brand: 'bg-brand-500',
  neutral: 'bg-ink-400',
}

export default function FeedbackBadge({
  tone = 'neutral',
  dot = true,
  children,
  className = '',
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset transition-colors duration-300 ${FEEDBACK_TONES[tone]} ${className}`}
    >
      {dot && <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${DOT_TONES[tone]}`} />}
      {children}
    </span>
  )
}