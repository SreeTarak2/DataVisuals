import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'

const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

const API_BASE_URL = 'http://localhost:8000'

// Configure axios defaults
axios.defaults.baseURL = API_BASE_URL

// Add request interceptor to include auth token
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Add response interceptor to handle token expiration
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token')
      const savedUser = localStorage.getItem('user')
      
      if (token && savedUser) {
        try {
          // Verify token is still valid
          const response = await axios.get('/auth/me')
          setUser(response.data)
          setIsAuthenticated(true)
        } catch (error) {
          // Token is invalid, clear storage
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          setUser(null)
          setIsAuthenticated(false)
        }
      }
      setLoading(false)
    }

    initAuth()
  }, [])

  const login = async (email, password) => {
    try {
      const response = await axios.post('/auth/login', {
        email,
        password
      })
      
      const { access_token, ...tokenData } = response.data
      
      // Store token and user data
      localStorage.setItem('access_token', access_token)
      
      // Get user info
      const userResponse = await axios.get('/auth/me')
      const userData = userResponse.data
      
      localStorage.setItem('user', JSON.stringify(userData))
      setUser(userData)
      setIsAuthenticated(true)
      
      return { success: true, user: userData }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      }
    }
  }

  const register = async (userData) => {
    try {
      const response = await axios.post('/auth/register', userData)
      
      // Registration successful, now try to auto-login
      try {
        const loginResult = await login(userData.email, userData.password)
        if (loginResult.success) {
          return { success: true, user: loginResult.user, message: 'Account created successfully!' }
        } else {
          // Registration succeeded but auto-login failed
          return { 
            success: true, 
            user: response.data, 
            message: 'Account created successfully! Please log in.',
            needsLogin: true 
          }
        }
      } catch (loginError) {
        // Registration succeeded but auto-login failed
        return { 
          success: true, 
          user: response.data, 
          message: 'Account created successfully! Please log in.',
          needsLogin: true 
        }
      }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      }
    }
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setUser(null)
    setIsAuthenticated(false)
  }

  const updateProfile = async (profileData) => {
    try {
      const response = await axios.put('/auth/profile', profileData)
      const updatedUser = response.data
      
      localStorage.setItem('user', JSON.stringify(updatedUser))
      setUser(updatedUser)
      
      return { success: true, user: updatedUser }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Profile update failed'
      }
    }
  }

  const changePassword = async (oldPassword, newPassword) => {
    try {
      await axios.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      
      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Password change failed'
      }
    }
  }

  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    updateProfile,
    changePassword
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}



