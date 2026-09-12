import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { AuthShell } from './authShell'
import { Button, ErrorNote, Field, Input } from '../components/ui'

const MIN_PASSWORD_LENGTH = 8

export default function Register() {
  const { signUp, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to="/" replace />

  function update(field) {
    return (event) => {
      setForm((previous) => ({ ...previous, [field]: event.target.value }))
      setFieldErrors((previous) => ({ ...previous, [field]: undefined }))
    }
  }

  /** Catch locally what the server would reject, so the round trip is not wasted. */
  function validate() {
    const errors = {}
    if (!form.full_name.trim()) errors.full_name = 'Tell us what to call you'
    if (form.password.length < MIN_PASSWORD_LENGTH) {
      errors.password = `At least ${MIN_PASSWORD_LENGTH} characters`
    }
    if (new TextEncoder().encode(form.password).length > 72) {
      errors.password = 'That password is too long (72 bytes maximum)'
    }
    if (form.confirm !== form.password) errors.confirm = 'The passwords do not match'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    if (!validate()) return

    setSubmitting(true)
    try {
      await signUp({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      // Straight to the profile: an interview is only as good as what it knows.
      navigate('/profile', { replace: true })
    } catch (exception) {
      setError(exception)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="It takes a minute, then upload a resume and start."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-600 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <ErrorNote error={error} />

        <Field label="Full name" htmlFor="full_name" error={fieldErrors.full_name}>
          <Input
            id="full_name"
            autoComplete="name"
            required
            value={form.full_name}
            onChange={update('full_name')}
            placeholder="Ada Lovelace"
          />
        </Field>

        <Field label="Email" htmlFor="email" error={fieldErrors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update('email')}
            placeholder="you@example.com"
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters`}
          error={fieldErrors.password}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={update('password')}
          />
        </Field>

        <Field label="Confirm password" htmlFor="confirm" error={fieldErrors.confirm}>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm}
            onChange={update('confirm')}
          />
        </Field>

        <Button type="submit" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthShell>
  )
}
