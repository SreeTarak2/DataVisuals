import React, { createContext, useContext, useState, useEffect } from 'react'

interface ThemeContextType {
  isDarkTheme: boolean
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

interface ThemeProviderProps {
  children: React.ReactNode
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    // Check localStorage for saved theme preference
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme) {
      return savedTheme === 'dark'
    }
    // Default to light theme for better aesthetics
    return false
  })

  const toggleTheme = () => {
    setIsDarkTheme(!isDarkTheme)
  }

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light')
  }, [isDarkTheme])

  const value = {
    isDarkTheme,
    toggleTheme
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}
