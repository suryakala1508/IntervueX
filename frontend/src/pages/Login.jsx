import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { AuthShell } from './authShell'
import { Button, ErrorNote, Field, Input } from '../components/ui'

export default function Login() {
  const { signIn, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to={location.state?.from ?? '/'} replace />

  function update(field) {
    return (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signIn(form)
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (exception) {
      setError(exception)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to continue practising."
      footer={
        <>
          New here?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <ErrorNote error={error} />

        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update('email')}
            placeholder="you@example.com"
          />
        </Field>

        <Field label="Password" htmlFor="password">
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={update('password')}
            placeholder="********"
          />
        </Field>

        <Button type="submit" className="w-full" loading={submitting} disabled={isLoading}>
          Sign in
        </Button>
      </form>
    </AuthShell>
  )
}
