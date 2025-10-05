import React from 'react'
import { NavLink } from 'react-router-dom'
import { 
  BarChart3, 
  Database, 
  Brain, 
  PieChart, 
  Lightbulb, 
  Settings,
  Home
} from 'lucide-react'

const Sidebar = () => {
  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: Home },
    { name: 'Datasets', href: '/dashboard/datasets', icon: Database },
    { name: 'Analysis', href: '/dashboard/analysis', icon: Brain },
    { name: 'Charts', href: '/dashboard/charts', icon: PieChart },
    { name: 'Settings', href: '/dashboard/settings', icon: Settings },
  ]

  return (
    <div className="w-64 bg-gradient-to-b from-slate-900 to-gray-900 border-r border-slate-700 flex flex-col shadow-2xl">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center shadow-lg">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">DataSage AI</h1>
            <p className="text-xs text-slate-400">v2.0</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              `flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-emerald-500/20 text-emerald-300 border-r-2 border-emerald-500 shadow-lg shadow-emerald-500/10'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-400 text-center">
          AI-Powered Data Visualization
        </div>
      </div>
    </div>
  )
}

export default Sidebar



