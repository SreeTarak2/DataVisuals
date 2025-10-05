import React, { useState } from 'react'
import { Bell, User, Menu, X, LogOut, Settings } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

const Header = () => {
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <header className="bg-gradient-to-r from-slate-900 to-gray-900 border-b border-slate-700 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Mobile menu button */}
        <button
          className="md:hidden p-2 rounded-md text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        >
          {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>

        {/* Logo/Brand - Left side */}
        <div className="flex items-center">
          <h1 className="text-xl font-bold text-white">DataSage</h1>
        </div>

        {/* Right side - Profile and Notifications */}
        <div className="flex items-center space-x-4">
          {/* Notifications */}
          <button className="p-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-colors">
            <Bell className="w-5 h-5" />
          </button>

          {/* Profile */}
          <div className="relative">
            <button
              className="flex items-center space-x-2 p-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              onClick={() => setIsProfileOpen(!isProfileOpen)}
            >
              <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center text-white font-semibold text-sm shadow-lg">
                {getInitials(user?.full_name || user?.username)}
              </div>
              <div className="hidden md:block text-left">
                <div className="text-sm font-medium text-white">
                  {user?.full_name || user?.username || 'User'}
                </div>
                <div className="text-xs text-slate-400">
                  {user?.email}
                </div>
              </div>
            </button>

            {/* Profile dropdown */}
            {isProfileOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-slate-800 rounded-xl shadow-2xl py-2 z-50 border border-slate-600 backdrop-blur-sm">
                <button
                  onClick={() => {
                    navigate('/dashboard/settings')
                    setIsProfileOpen(false)
                  }}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
                >
                  <User className="w-4 h-4" />
                  <span>Profile</span>
                </button>
                
                <button
                  onClick={() => {
                    navigate('/dashboard/settings')
                    setIsProfileOpen(false)
                  }}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
                >
                  <Settings className="w-4 h-4" />
                  <span>Settings</span>
                </button>
                
                <hr className="my-2 border-slate-600" />
                
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-sm text-red-400 hover:bg-red-900/20 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Click outside to close dropdown */}
      {isProfileOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsProfileOpen(false)}
        />
      )}
    </header>
  )
}

export default Header
