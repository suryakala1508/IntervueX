import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Button } from './ui'
import ConfirmDialog from './ConfirmDialog'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/interviews', label: 'Interviews' },
  { to: '/profile', label: 'Profile' },
  { to: '/jobs', label: 'Target roles' },
  { to: '/documents', label: 'Documents' },
]

function Logo() {
  return (
    <span className="font-display flex items-center gap-2 text-base font-bold tracking-tight text-ink-900">
      <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-amber-500 text-xs font-bold text-white shadow-md shadow-brand-500/30">
        iX
      </span>
      IntervueX
    </span>
  )
}

function navClass({ isActive }) {
  return `rounded-full px-4 py-2 text-sm font-medium transition-all duration-300 ${
    isActive
      ? 'bg-brand-100 text-brand-700 shadow-sm'
      : 'text-ink-600 hover:bg-cream-200/70 hover:text-ink-900'
  }`
}

function LogOutIcon() {
  return (
    <svg
      className="h-6 w-6"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
      />
    </svg>
  )
}

export default function Layout() {
  const { user, isAdmin, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [logOutOpen, setLogOutOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  const items = isAdmin ? [...NAV_ITEMS, { to: '/admin', label: 'Admin' }] : NAV_ITEMS

  async function handleLogOut() {
    setLoggingOut(true)
    await signOut()
    navigate('/login')
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-ink-200/60 bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <Logo />
            <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
              {items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-ink-500 sm:inline">{user?.full_name}</span>
            <Button variant="secondary" size="sm" onClick={() => setLogOutOpen(true)}>
              Log out
            </Button>
            <button
              type="button"
              className="rounded-full p-2 text-ink-600 transition-colors hover:bg-cream-200/70 md:hidden"
              aria-expanded={menuOpen}
              aria-label="Toggle navigation"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeWidth="2"
                  d={menuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 7h16M4 12h16M4 17h16'}
                />
              </svg>
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav
            className="flex flex-col gap-1 border-t border-ink-100 px-4 py-2 md:hidden"
            aria-label="Main"
          >
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={navClass}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <div key={location.pathname} className="animate-fade-in-up">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-ink-200/60 bg-white/40">
        <div className="mx-auto max-w-6xl px-4 py-5 text-xs text-ink-500">
          IntervueX – adaptive interview practice grounded in your own resume and target role.
        </div>
      </footer>

      <ConfirmDialog
        open={logOutOpen}
        title="Log out?"
        message="Are you sure you want to log out? You'll need to sign in again to continue."
        confirmLabel="Log out"
        cancelLabel="Cancel"
        tone="danger"
        busy={loggingOut}
        onConfirm={handleLogOut}
        onCancel={() => setLogOutOpen(false)}
        icon={<LogOutIcon />}
      />
    </div>
  )
}