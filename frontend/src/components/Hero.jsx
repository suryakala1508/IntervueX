/**
 * Welcoming page-topper: headline, supporting line, and an abstract blob /
 * gradient backdrop with a soft conversational illustration. Not a plain card.
 */

export default function Hero({ eyebrow, title, subtitle, children, className = '' }) {
  return (
    <section
      className={`relative isolate overflow-hidden rounded-[28px] px-6 py-14 shadow-soft sm:px-12 sm:py-18 ${className}`}
    >
      {/* Warm wash the hero sits on */}
      <div
        aria-hidden
        className="absolute inset-0 -z-20 bg-gradient-to-br from-brand-100 via-cream-100 to-amber-100"
      />

      {/* Abstract blobs drifting behind the copy */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-brand-300/40 blur-3xl animate-float-slow" />
        <div className="absolute -bottom-28 -left-16 h-80 w-80 rounded-full bg-amber-300/40 blur-3xl animate-float-slow [animation-delay:-4s]" />

        <svg
          className="absolute -right-10 top-1/2 h-48 w-48 -translate-y-1/2 opacity-70 sm:h-64 sm:w-64"
          viewBox="0 0 200 200"
          fill="none"
        >
          <circle cx="145" cy="62" r="34" fill="currentColor" className="text-brand-200/70" />
          <path
            d="M52 96c0-18 15-32 34-32h24c19 0 34 14 34 32v36c0 18-15 32-34 32H86c-19 0-34-14-34-32v-36z"
            fill="currentColor"
            className="text-white/90"
            stroke="currentColor"
            strokeOpacity="0.35"
            strokeWidth="3"
          />
          <circle cx="84" cy="116" r="4" fill="currentColor" className="text-brand-400/80" />
          <circle cx="106" cy="116" r="4" fill="currentColor" className="text-brand-400/80" />
          <circle cx="128" cy="116" r="4" fill="currentColor" className="text-brand-400/80" />
          <path
            d="M92 148h32"
            stroke="currentColor"
            strokeOpacity="0.35"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle cx="40" cy="150" r="10" fill="currentColor" className="text-amber-300/80" />
        </svg>
      </div>

      {/* Soft dotscape under everything */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 opacity-60"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(120,60,25,0.07) 1px, transparent 1px)',
          backgroundSize: '18px 18px',
        }}
      />

      <div className="mx-auto max-w-2xl animate-fade-in-up text-center">
        {eyebrow && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-brand-700 ring-1 ring-inset ring-brand-500/25">
            {eyebrow}
          </span>
        )}
        <h1 className="mt-5 text-3xl font-bold text-ink-900 sm:text-5xl">{title}</h1>
        {subtitle && (
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-ink-600 sm:text-lg">
            {subtitle}
          </p>
        )}
        {children && (
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">{children}</div>
        )}
      </div>
    </section>
  )
}