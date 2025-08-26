import React from 'react'
import { User, Brain } from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'

const PersonaSwitcher: React.FC = () => {
  const { persona, setPersona } = usePersona()

  return (
    <div className="rounded-lg border border-secondary-200 bg-secondary-50 p-4">
      <h3 className="text-sm font-medium text-secondary-900 mb-3">Persona Mode</h3>
      
      <div className="space-y-2">
        <button
          onClick={() => setPersona('normal')}
          className={`w-full flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            persona === 'normal'
              ? 'bg-primary-50 text-primary-700 border border-primary-200'
              : 'text-secondary-600 hover:bg-white hover:text-secondary-900'
          }`}
        >
          <User className="h-4 w-4" />
          <span>Business User</span>
          {persona === 'normal' && (
            <div className="ml-auto h-2 w-2 rounded-full bg-primary-600" />
          )}
        </button>
        
        <button
          onClick={() => setPersona('expert')}
          className={`w-full flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            persona === 'expert'
              ? 'bg-accent-50 text-accent-700 border border-accent-200'
              : 'text-secondary-600 hover:bg-white hover:text-secondary-900'
          }`}
        >
          <Brain className="h-4 w-4" />
          <span>Data Expert</span>
          {persona === 'expert' && (
            <div className="ml-auto h-2 w-2 rounded-full bg-accent-600" />
          )}
        </button>
      </div>
      
      <div className="mt-3 text-xs text-secondary-500">
        {persona === 'normal' ? (
          <p>Simple explanations and business insights</p>
        ) : (
          <p>Technical analysis and statistical depth</p>
        )}
      </div>
    </div>
  )
}

export default PersonaSwitcher
