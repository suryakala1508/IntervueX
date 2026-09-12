/** The split marketing/form frame shared by the sign-in and sign-up pages. */

const SELLING_POINTS = [
  {
    icon: '📄',
    title: 'Grounded in your own material',
    body: 'Questions are retrieved from your resume and the job description you are targeting, not from a generic question bank.',
  },
  {
    icon: '🪜',
    title: 'It adapts as you answer',
    body: 'A strong answer earns a harder follow-up. A shaky one steps back to fundamentals instead of piling on.',
  },
  {
    icon: '📊',
    title: 'Scored against a fixed rubric',
    body: 'Correctness, relevance, clarity, completeness, and communication - every answer, every time, so progress is comparable.',
  },
]

function BrandMark({ light }) {
  return (
    <span
      className={`font-display flex items-center gap-2 text-lg font-bold tracking-tight ${
        light ? 'text-white' : 'text-ink-900'
      }`}
    >
      <span
        className={`grid h-9 w-9 place-items-center rounded-full text-xs font-bold shadow-md ${
          light
            ? 'bg-white/20 text-white'
            : 'bg-gradient-to-br from-brand-500 to-amber-500 text-white shadow-brand-500/30'
        }`}
      >
        iX
      </span>
      IntervueX
    </span>
  )
}

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <aside className="relative isolate hidden overflow-hidden bg-gradient-to-br from-brand-600 via-brand-500 to-amber-500 px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
          <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-amber-300/40 blur-3xl animate-float-slow" />
          <div className="absolute -bottom-24 -left-16 h-72 w-72 rounded-full bg-rose-300/40 blur-3xl animate-float-slow [animation-delay:-4s]" />
          <div
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                'radial-gradient(circle, rgba(255,255,255,0.35) 1px, transparent 1px)',
              backgroundSize: '22px 22px',
            }}
          />
        </div>

        <BrandMark light />

        <div className="max-w-md">
          <h2 className="text-4xl font-bold leading-tight tracking-tight">
            Practise the interview you are actually about to have.
          </h2>
          <ul className="mt-10 space-y-6">
            {SELLING_POINTS.map((point) => (
              <li key={point.title} className="flex gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white/15 text-xl">
                  {point.icon}
                </span>
                <div>
                  <p className="text-base font-semibold">{point.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-white/85">{point.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-sm text-white/75">
          Your resume and answers stay in your own account.
        </p>
      </aside>

      <main className="relative flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm animate-fade-in-up">
          <div className="mb-8 lg:hidden">
            <BrandMark />
          </div>

          <div className="rounded-[24px] border border-ink-200/70 bg-white/85 p-8 shadow-soft backdrop-blur">
            <h1 className="text-2xl font-bold tracking-tight text-ink-900">{title}</h1>
            {subtitle && <p className="mt-1.5 mb-6 text-sm text-ink-500">{subtitle}</p>}

            {children}

            {footer && <p className="mt-6 text-center text-sm text-ink-500">{footer}</p>}
          </div>
        </div>
      </main>
    </div>
  )
}