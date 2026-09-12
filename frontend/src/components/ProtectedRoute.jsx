import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Loading } from './ui'

/**
 * Gate for authenticated routes. While the stored token is being validated it
 * renders a spinner rather than redirecting, so a page refresh does not bounce
 * a signed-in user to the sign-in screen.
 */
export default function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <Loading label="Checking your session" />

  if (!isAuthenticated) {
    // Remember where they were headed so sign-in can send them back.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (requireAdmin && !isAdmin) return <Navigate to="/" replace />

  return children
}
