import { Routes, Route, Navigate } from 'react-router-dom'
import { CssBaseline } from '@mui/material'
import { useTheme } from './context/ThemeContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Bookings from './pages/Bookings'
import Tours from './pages/Tours'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

function App() {
  const { theme } = useTheme()

  return (
    <>
      <CssBaseline />
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="reservas" element={<Bookings />} />
          <Route path="tours" element={<Tours />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="configuracion" element={
            <ProtectedRoute requiredRole="admin">
              <Settings />
            </ProtectedRoute>
          } />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default App
