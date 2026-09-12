/** A friendly "get set up" guide: three warm steps shown as soft cards. */

const DEFAULT_STEPS = [
  {
    icon: '🧑‍💻',
    title: 'Fill in your profile',
    body: 'Add your skills, experience, and projects. These feed every question you get asked.',
    href: '/profile',
    cta: 'Open profile',
  },
  {
    icon: '🎯',
    title: 'Save a target role',
    body: 'Paste the job posting you are aiming at so questions follow the responsibilities and requirements.',
    href: '/jobs',
    cta: 'Add a role',
  },
  {
    icon: '🎙️',
    title: 'Practise like it is the real thing',
    body: 'Start an interview, answer out loud or in writing, and get instant coaching on your answer.',
    href: null,
    cta: null,
  },
]

export default function SetupGuide({ steps = DEFAULT_STEPS }) {
  return (
    <ol className="grid gap-5 sm:grid-cols-3">
      {steps.map((step, index) => (
        <li key={step.title}>
          <div className="h-full rounded-[20px] border border-ink-200/70 bg-white/80 p-6 shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift">
            <div className="flex items-center justify-between">
              <span className="text-3xl">{step.icon}</span>
              <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 text-sm font-bold text-brand-700 ring-1 ring-inset ring-brand-500/20">
                {index + 1}
              </span>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-ink-900">{step.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{step.body}</p>
            {step.href && (
              <a
                href={step.href}
                className="mt-4 inline-block text-sm font-semibold text-brand-600 transition-colors hover:text-brand-700"
              >
                {step.cta} →
              </a>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}