import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Login from './Login'
import Register from './Register'
import { renderWithProviders } from '../test/renderWithProviders'
import { api, tokens } from '../lib/api'

describe('Login', () => {
  it('shows the fields a sign-in needs', () => {
    renderWithProviders(<Login />)

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('signs in and stores the returned tokens', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.auth, 'login').mockResolvedValue({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      expires_in: 1800,
    })
    vi.spyOn(api.auth, 'me').mockResolvedValue({
      id: '1',
      email: 'ada@example.com',
      full_name: 'Ada Lovelace',
      role: 'candidate',
      is_active: true,
    })

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(api.auth.login).toHaveBeenCalledWith({
        email: 'ada@example.com',
        password: 'password123',
      })
    })
    await waitFor(() => expect(tokens.access).toBe('access-1'))
  })

  it('shows the server message when the credentials are wrong', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.auth, 'login').mockRejectedValue(new Error('Incorrect email or password'))

    renderWithProviders(<Login />)

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
  })

  it('offers a way to reach the sign-up page', () => {
    renderWithProviders(<Login />)
    expect(screen.getByRole('link', { name: /create an account/i })).toHaveAttribute(
      'href',
      '/register',
    )
  })
})

describe('Register', () => {
  it('rejects a password that is too short before calling the API', async () => {
    const user = userEvent.setup()
    const register = vi.spyOn(api.auth, 'register')

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Ada Lovelace')
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'short')
    await user.type(screen.getByLabelText(/confirm password/i), 'short')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })

  it('rejects mismatched passwords before calling the API', async () => {
    const user = userEvent.setup()
    const register = vi.spyOn(api.auth, 'register')

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), 'Ada Lovelace')
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password456')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/do not match/i)).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })

  it('registers when the form is valid', async () => {
    const user = userEvent.setup()
    vi.spyOn(api.auth, 'register').mockResolvedValue({
      access_token: 'a',
      refresh_token: 'r',
      expires_in: 1800,
    })
    vi.spyOn(api.auth, 'me').mockResolvedValue({
      id: '1',
      email: 'ada@example.com',
      full_name: 'Ada Lovelace',
      role: 'candidate',
      is_active: true,
    })

    renderWithProviders(<Register />)

    await user.type(screen.getByLabelText(/full name/i), '  Ada Lovelace  ')
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(api.auth.register).toHaveBeenCalledWith({
        full_name: 'Ada Lovelace',
        email: 'ada@example.com',
        password: 'password123',
      })
    })
  })
})
