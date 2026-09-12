import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../context/AuthContext'

/**
 * Render a component inside the router and auth providers it expects.
 *
 * Pass `path` and `route` together when the component reads URL parameters.
 */
export function renderWithProviders(
  ui,
  { route = '/', path = null, withAuth = true } = {},
) {
  const content = path ? (
    <Routes>
      <Route path={path} element={ui} />
    </Routes>
  ) : (
    ui
  )

  return render(
    <MemoryRouter initialEntries={[route]}>
      {withAuth ? <AuthProvider>{content}</AuthProvider> : content}
    </MemoryRouter>,
  )
}
