/** Friendly, encouraging empty state with a soft illustration and an optional action. */

export default function EmptyState({ icon = '🎯', title, description, action, className = '' }) {
  return (
    <div
      className={`animate-fade-in-up rounded-[20px] border-2 border-dashed border-ink-200/80 bg-white/70 px-6 py-16 text-center shadow-soft ${className}`}
    >
      <div
        aria-hidden
        className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-brand-100 text-3xl"
      >
        {icon}
      </div>
      <h3 className="mt-5 text-xl font-semibold text-ink-900">{title}</h3>
      {description && (
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-600">
          {description}
        </p>
      )}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  )
}