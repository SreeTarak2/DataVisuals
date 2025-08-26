import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { PersonaProvider } from './contexts/PersonaContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Datasets from './pages/Datasets'
import Analysis from './pages/Analysis'
import Templates from './pages/Templates'
import NotFound from './pages/NotFound'

function App() {
  return (
    <PersonaProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </PersonaProvider>
  )
}

export default App
