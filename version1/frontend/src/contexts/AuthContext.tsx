import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import axios from 'axios'

interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  last_login: string | null
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<boolean>
  register: (email: string, fullName: string, password: string) => Promise<boolean>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Check for existing auth on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      setToken(storedToken)
      setUser(JSON.parse(storedUser))
      
      // Verify token is still valid
      verifyToken(storedToken)
    } else {
      setLoading(false)
    }
  }, [])

  const verifyToken = async (tokenToVerify: string) => {
    try {
      const response = await axios.get('http://localhost:8000/auth/me', {
        headers: {
          Authorization: `Bearer ${tokenToVerify}`
        }
      })
      setUser(response.data)
    } catch (error) {
      // Token is invalid, clear auth
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await axios.post('http://localhost:8000/auth/login', {
        email,
        password
      })

      const { access_token, user: userData } = response.data
      
      localStorage.setItem('token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
      
      setToken(access_token)
      setUser(userData)
      
      return true
    } catch (error) {
      console.error('Login error:', error)
      return false
    }
  }

  const register = async (email: string, fullName: string, password: string): Promise<boolean> => {
    try {
      await axios.post('http://localhost:8000/auth/register', {
        email,
        full_name: fullName,
        password
      })
      return true
    } catch (error) {
      console.error('Registration error:', error)
      return false
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
    loading
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}