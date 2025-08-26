import React, { createContext, useContext, useState, ReactNode } from 'react'

export type PersonaType = 'normal' | 'expert'

interface PersonaContextType {
  persona: PersonaType
  setPersona: (persona: PersonaType) => void
  isNormal: boolean
  isExpert: boolean
}

const PersonaContext = createContext<PersonaContextType | undefined>(undefined)

export const usePersona = () => {
  const context = useContext(PersonaContext)
  if (context === undefined) {
    throw new Error('usePersona must be used within a PersonaProvider')
  }
  return context
}

interface PersonaProviderProps {
  children: ReactNode
}

export const PersonaProvider: React.FC<PersonaProviderProps> = ({ children }) => {
  const [persona, setPersona] = useState<PersonaType>('normal')

  const value: PersonaContextType = {
    persona,
    setPersona,
    isNormal: persona === 'normal',
    isExpert: persona === 'expert',
  }

  return (
    <PersonaContext.Provider value={value}>
      {children}
    </PersonaContext.Provider>
  )
}
