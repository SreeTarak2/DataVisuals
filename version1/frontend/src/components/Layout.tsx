import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  Brain, 
  BarChart3, 
  Database, 
  PieChart, 
  FileText, 
  Settings, 
  Menu, 
  X, 
  Search, 
  Upload, 
  Bell, 
  Moon, 
  Sun, 
  User, 
  ChevronDown,
  LogOut,
  TrendingUp,
  Activity
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

interface LayoutProps {
  children: React.ReactNode
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)
  const [showProfileDropdown, setShowProfileDropdown] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const { user, logout } = useAuth()
  const { isDarkTheme, toggleTheme } = useTheme()
  const location = useLocation()

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (!target.closest('.profile-dropdown') && !target.closest('.notification-dropdown')) {
        setShowProfileDropdown(false)
        setShowNotifications(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const navigation = [
    { name: 'Dashboard', href: '/', icon: BarChart3, current: location.pathname === '/' },
    { name: 'Data Explorer', href: '/datasets', icon: Database, current: location.pathname === '/datasets' },
    { name: 'Analysis', href: '/analysis', icon: TrendingUp, current: location.pathname === '/analysis' },
    { name: 'Charts', href: '/charts', icon: PieChart, current: location.pathname === '/charts' },
  ]

  const handleLogout = () => {
    logout()
    setShowProfileDropdown(false)
  }

  return (
    <div className={`min-h-screen ${isDarkTheme ? 'bg-gray-900' : 'bg-gray-50'}`}>
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white">
          <div className="absolute top-0 right-0 -mr-12 pt-2">
            <button
              type="button"
              className="ml-1 flex items-center justify-center h-10 w-10 rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
          onClick={() => setSidebarOpen(false)}
            >
              <X className="h-6 w-6 text-white" />
            </button>
          </div>
          <div className="flex-1 h-0 pt-5 pb-4 overflow-y-auto">
            <div className="flex-shrink-0 flex items-center px-4">
              <Brain className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">DataSage AI</span>
            </div>
            <nav className="mt-5 px-2 space-y-1">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`${
                    item.current
                      ? 'bg-blue-100 text-blue-900'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  } group flex items-center px-2 py-2 text-base font-medium rounded-md`}
                >
                  <item.icon
                    className={`${
                      item.current ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-500'
                    } mr-4 h-6 w-6`}
                  />
                  {item.name}
                </Link>
              ))}
            </nav>
                </div>
              </div>
            </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:flex-shrink-0">
        <div className="flex flex-col w-64">
          <div className="flex flex-col h-0 flex-1 bg-white border-r border-gray-200">
            <div className="flex-1 flex flex-col pt-5 pb-4 overflow-y-auto">
              <div className="flex items-center flex-shrink-0 px-4">
                <Brain className="h-8 w-8 text-blue-600" />
                <span className="ml-2 text-xl font-bold text-gray-900">DataSage AI</span>
              </div>
              <nav className="mt-5 flex-1 px-2 space-y-1">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                    className={`${
                      item.current
                        ? 'bg-blue-100 text-blue-900'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    } group flex items-center px-2 py-2 text-sm font-medium rounded-md`}
                  >
                    <item.icon
                      className={`${
                        item.current ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-500'
                      } mr-3 h-6 w-6`}
                    />
                          {item.name}
                    </Link>
                  ))}
              </nav>
            </div>
            </div>
          </div>
        </div>

        {/* Main content */}
      <div className="lg:pl-64 flex flex-col flex-1">
        {/* Top navigation */}
        <div className="sticky top-0 z-10 flex-shrink-0 flex h-16 bg-white border-b border-gray-200">
                  <button
            type="button"
            className="px-4 border-r border-gray-200 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
                  </button>
          <div className="flex-1 px-4 flex justify-between">
            <div className="flex-1 flex">
              <div className="w-full flex md:ml-0">
                <div className="relative w-full text-gray-400 focus-within:text-gray-600">
                  <div className="absolute inset-y-0 left-0 flex items-center pointer-events-none">
                    <Search className="h-5 w-5" />
                    </div>
                    <input
                    id="search-field"
                    className="block w-full h-full pl-8 pr-3 py-2 border-transparent text-gray-900 placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-0 focus:border-transparent"
                    placeholder="Search datasets, charts, insights..."
                    type="search"
                      onFocus={() => setSearchFocused(true)}
                      onBlur={() => setSearchFocused(false)}
                  />
                </div>
              </div>
            </div>
            <div className="ml-4 flex items-center md:ml-6">
              {/* Upload button */}
              <button
                type="button"
                className="bg-blue-600 p-1 rounded-full text-white hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mr-3"
              >
                <Upload className="h-6 w-6" />
              </button>

              {/* Theme toggle */}
              <button
                type="button"
                className="bg-gray-100 p-1 rounded-full text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mr-3"
                onClick={toggleTheme}
              >
                {isDarkTheme ? <Sun className="h-6 w-6" /> : <Moon className="h-6 w-6" />}
              </button>

              {/* Notifications */}
              <div className="relative">
                <button
                  type="button"
                  className="bg-gray-100 p-1 rounded-full text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mr-3"
                      onClick={() => setShowNotifications(!showNotifications)}
                >
                  <Bell className="h-6 w-6" />
                </button>
                {showNotifications && (
                  <div className="notification-dropdown absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg py-1 z-50">
                    <div className="px-4 py-2 text-sm text-gray-500">Notifications</div>
                    <div className="px-4 py-2 text-sm text-gray-600">No new notifications</div>
                  </div>
                )}
                  </div>

              {/* Profile dropdown */}
              <div className="relative">
                  <button
                  type="button"
                  className="max-w-xs bg-white flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  onClick={() => setShowProfileDropdown(!showProfileDropdown)}
                >
                  <span className="sr-only">Open user menu</span>
                  <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center">
                    <User className="h-5 w-5 text-white" />
                  </div>
                  <ChevronDown className="ml-2 h-4 w-4 text-gray-400" />
                  </button>
                {showProfileDropdown && (
                  <div className="profile-dropdown absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50">
                    <div className="px-4 py-2 text-sm text-gray-700 border-b">
                      {user?.full_name || user?.email}
                    </div>
                    <Link
                      to="/settings"
                      className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      onClick={() => setShowProfileDropdown(false)}
                    >
                      Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    >
                      Sign out
                    </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

          {/* Page content */}
        <main className="flex-1">
              {children}
          </main>
      </div>
    </div>
  )
}

export default Layout