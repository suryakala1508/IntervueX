import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Admin from './pages/Admin'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import InterviewDetail from './pages/InterviewDetail'
import InterviewRoom from './pages/InterviewRoom'
import Interviews from './pages/Interviews'
import Jobs from './pages/Jobs'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Profile from './pages/Profile'
import Register from './pages/Register'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="documents" element={<Documents />} />
        <Route path="interviews" element={<Interviews />} />
        <Route path="interviews/:interviewId" element={<InterviewDetail />} />
        <Route
          path="admin"
          element={
            <ProtectedRoute requireAdmin>
              <Admin />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* The interview room is full-screen: no nav to click away mid-question. */}
      <Route
        path="/interviews/:interviewId/room"
        element={
          <ProtectedRoute>
            <InterviewRoom />
          </ProtectedRoute>
        }
      />

      <Route path="/404" element={<NotFound />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  )
}
