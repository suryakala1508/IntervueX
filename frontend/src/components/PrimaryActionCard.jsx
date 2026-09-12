/**
 * The main interaction card of the app — the thing we most want someone to do.
 * Generously padded, softly shadowed, with a gentle hover lift.
 */

export default function PrimaryActionCard({
  icon = '🎙️',
  title,
  description,
  action,
  className = '',
}) {
  return (
    <div
      className={`group relative overflow-hidden rounded-[28px] border border-ink-200/70 bg-white p-8 shadow-soft transition-all duration-300 hover:-translate-y-1 hover:shadow-lift sm:p-10 ${className}`}
    >
      <div
        aria-hidden
        className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-200/50 blur-3xl transition-opacity duration-300 group-hover:opacity-100"
      />
      <div
        aria-hidden
        className="absolute -bottom-20 -left-14 h-56 w-56 rounded-full bg-amber-200/50 blur-3xl"
      />

      <div className="relative flex flex-col items-center gap-5 text-center">
        {icon && (
          <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-brand-100 to-amber-100 text-3xl ring-1 ring-inset ring-brand-500/20">
            {icon}
          </div>
        )}
        <h2 className="text-2xl font-bold text-ink-900">{title}</h2>
        {description && (
          <p className="max-w-xl text-base leading-relaxed text-ink-600">{description}</p>
        )}
        {action && <div className="mt-2 flex justify-center">{action}</div>}
      </div>
    </div>
  )
}