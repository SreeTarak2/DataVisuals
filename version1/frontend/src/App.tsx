import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Analysis from './pages/Analysis'
import Charts from './pages/Charts'
import DataExplorer from './pages/DataExplorer'
import NotFound from './pages/NotFound'

// Loading Component
const LoadingScreen: React.FC = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="text-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
      <p className="text-gray-600">Loading...</p>
    </div>
  </div>
)

// App Routes Component
const AppRoutes: React.FC = () => {
  const { user, loading } = useAuth()
  
  if (loading) {
    return <LoadingScreen />
  }
  
  return (
    <Routes>
      {!user ? (
        <>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<LandingPage />} />
        </>
      ) : (
        <Route path="*" element={
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/datasets" element={<DataExplorer />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/charts" element={<Charts />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Layout>
        } />
      )}
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <AppRoutes />
      </ThemeProvider>
    </AuthProvider>
  )
}

export default App
