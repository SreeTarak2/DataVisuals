import React, { useState } from 'react'
import { X, Mail, Lock, User, Brain, BarChart3, Sparkles, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
}

const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose }) => {
  const { login } = useAuth()
  const { isDarkTheme } = useTheme()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [selectedPersona, setSelectedPersona] = useState<'normal' | 'expert'>('normal')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      await login(email, password, selectedPersona)
      onClose()
      // Reset form
      setEmail('')
      setPassword('')
      setSelectedPersona('normal')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (!isLoading) {
      onClose()
      setError('')
      setEmail('')
      setPassword('')
      setSelectedPersona('normal')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />
      
      {/* Modal */}
      <div className={`relative w-full max-w-md ${isDarkTheme ? 'bg-slate-800' : 'bg-white'} rounded-2xl shadow-2xl border ${isDarkTheme ? 'border-slate-700' : 'border-gray-200'}`}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-slate-700">
          <div className="flex items-center space-x-2">
            <div className={`p-2 rounded-lg ${isDarkTheme ? 'bg-sky-500/20' : 'bg-sky-100'}`}>
              <Brain className={`h-6 w-6 ${isDarkTheme ? 'text-sky-400' : 'text-sky-600'}`} />
            </div>
            <h2 className={`text-xl font-bold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
              Welcome to DataSage AI
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className={`p-2 rounded-lg transition-colors ${isDarkTheme ? 'hover:bg-slate-700 text-gray-400 hover:text-gray-300' : 'hover:bg-gray-100 text-gray-400 hover:text-gray-600'} ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email Field */}
            <div>
              <label className={`block text-sm font-medium mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className={`h-5 w-5 ${isDarkTheme ? 'text-gray-400' : 'text-gray-400'}`} />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={`w-full pl-10 pr-4 py-3 border rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-colors ${
                    isDarkTheme 
                      ? 'bg-slate-700 border-slate-600 text-white placeholder-gray-400' 
                      : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
                  }`}
                  placeholder="Enter your email"
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <label className={`block text-sm font-medium mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className={`h-5 w-5 ${isDarkTheme ? 'text-gray-400' : 'text-gray-400'}`} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className={`w-full pl-10 pr-12 py-3 border rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-colors ${
                    isDarkTheme 
                      ? 'bg-slate-700 border-slate-600 text-white placeholder-gray-400' 
                      : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
                  }`}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showPassword ? (
                    <EyeOff className={`h-5 w-5 ${isDarkTheme ? 'text-gray-400' : 'text-gray-400'}`} />
                  ) : (
                    <Eye className={`h-5 w-5 ${isDarkTheme ? 'text-gray-400' : 'text-gray-400'}`} />
                  )}
                </button>
              </div>
            </div>

            {/* Persona Selection */}
            <div>
              <label className={`block text-sm font-medium mb-3 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
                Choose your experience level
              </label>
              <div className="grid grid-cols-1 gap-3">
                {/* Normal User Option */}
                <div
                  onClick={() => setSelectedPersona('normal')}
                  className={`p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                    selectedPersona === 'normal'
                      ? isDarkTheme
                        ? 'border-sky-500 bg-sky-500/10'
                        : 'border-sky-500 bg-sky-50'
                      : isDarkTheme
                        ? 'border-slate-600 hover:border-slate-500'
                        : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    <div className={`p-2 rounded-lg ${isDarkTheme ? 'bg-green-500/20' : 'bg-green-100'}`}>
                      <User className={`h-5 w-5 ${isDarkTheme ? 'text-green-400' : 'text-green-600'}`} />
                    </div>
                    <div className="flex-1">
                      <h3 className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        Business User
                      </h3>
                      <p className={`text-sm mt-1 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                        Simple, intuitive interface with plain English explanations
                      </p>
                    </div>
                    {selectedPersona === 'normal' && (
                      <div className={`w-5 h-5 rounded-full border-2 border-sky-500 bg-sky-500 flex items-center justify-center`}>
                        <div className="w-2 h-2 bg-white rounded-full"></div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Expert User Option */}
                <div
                  onClick={() => setSelectedPersona('expert')}
                  className={`p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                    selectedPersona === 'expert'
                      ? isDarkTheme
                        ? 'border-sky-500 bg-sky-500/10'
                        : 'border-sky-500 bg-sky-50'
                      : isDarkTheme
                        ? 'border-slate-600 hover:border-slate-500'
                        : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    <div className={`p-2 rounded-lg ${isDarkTheme ? 'bg-purple-500/20' : 'bg-purple-100'}`}>
                      <BarChart3 className={`h-5 w-5 ${isDarkTheme ? 'text-purple-400' : 'text-purple-600'}`} />
                    </div>
                    <div className="flex-1">
                      <h3 className={`font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                        Data Expert
                      </h3>
                      <p className={`text-sm mt-1 ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                        Advanced analytics with technical insights and detailed metrics
                      </p>
                    </div>
                    {selectedPersona === 'expert' && (
                      <div className={`w-5 h-5 rounded-full border-2 border-sky-500 bg-sky-500 flex items-center justify-center`}>
                        <div className="w-2 h-2 bg-white rounded-full"></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className={`p-3 rounded-lg ${isDarkTheme ? 'bg-red-500/20 border border-red-500/30' : 'bg-red-50 border border-red-200'}`}>
                <p className={`text-sm ${isDarkTheme ? 'text-red-300' : 'text-red-600'}`}>
                  {error}
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading || !email || !password}
              className={`w-full py-3 px-4 rounded-xl font-semibold text-white transition-all duration-200 flex items-center justify-center space-x-2 ${
                isLoading || !email || !password
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-700 hover:to-blue-700 shadow-lg hover:shadow-xl transform hover:scale-[1.02]'
              }`}
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  <span>Get Started with DataSage AI</span>
                </>
              )}
            </button>
          </form>

          {/* Demo Credentials */}
          <div className={`mt-6 p-4 rounded-lg ${isDarkTheme ? 'bg-slate-700/50' : 'bg-gray-50'}`}>
            <p className={`text-sm font-medium mb-2 ${isDarkTheme ? 'text-gray-300' : 'text-gray-700'}`}>
              Demo Credentials:
            </p>
            <p className={`text-xs ${isDarkTheme ? 'text-gray-400' : 'text-gray-600'}`}>
              Email: demo@datasage.com<br />
              Password: demo123
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginModal

