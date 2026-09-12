import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setSessionExpiredHandler, tokens } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // "loading" until we know whether the stored token is still good, so
  // protected routes do not flash the sign-in page on a refresh.
  const [status, setStatus] = useState('loading')

  const signOut = useCallback(async ({ callApi = true } = {}) => {
    if (callApi && tokens.access) {
      try {
        await api.auth.logout()
      } catch {
        /* the tokens are discarded either way */
      }
    }
    tokens.clear()
    setUser(null)
    setStatus('signed-out')
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(() => {
      tokens.clear()
      setUser(null)
      setStatus('signed-out')
    })
  }, [])

  useEffect(() => {
    let cancelled = false

    async function restore() {
      if (!tokens.access && !tokens.refresh) {
        setStatus('signed-out')
        return
      }
      try {
        const me = await api.auth.me()
        if (!cancelled) {
          setUser(me)
          setStatus('signed-in')
        }
      } catch {
        if (!cancelled) {
          tokens.clear()
          setStatus('signed-out')
        }
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  const applyTokens = useCallback(async (pair) => {
    tokens.set(pair)
    const me = await api.auth.me()
    setUser(me)
    setStatus('signed-in')
    return me
  }, [])

  const signIn = useCallback(
    async (credentials) => applyTokens(await api.auth.login(credentials)),
    [applyTokens],
  )

  const signUp = useCallback(
    async (details) => applyTokens(await api.auth.register(details)),
    [applyTokens],
  )

  const value = useMemo(
    () => ({
      user,
      status,
      isLoading: status === 'loading',
      isAuthenticated: status === 'signed-in',
      isAdmin: user?.role === 'admin',
      signIn,
      signUp,
      signOut,
      setUser,
    }),
    [user, status, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
