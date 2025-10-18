import React, { useState, useEffect, Fragment } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  BarChart3, 
  Database, 
  MessageSquare, 
  Settings, 
  Menu, 
  X,
  User,
  LogOut,
  Plus,
  Search,
  HelpCircle,
  Bell,
  Sun,
  Moon,
  ChevronDown
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

// Custom hook for theme management
const useTheme = () => {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove(theme === 'dark' ? 'light' : 'dark');
    root.classList.add(theme);
    localStorage.setItem('theme', theme);
    // Add data-theme attribute for index.css to target
    root.setAttribute('data-theme', theme);
  }, [theme]);

  return [theme, setTheme];
};

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const [theme, setTheme] = useTheme();

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: BarChart3 },
    { name: 'Datasets', href: '/datasets', icon: Database },
    { name: 'AI Chat', href: '/chat', icon: MessageSquare },
  ];

  const secondaryNavigation = [
    { name: 'Settings', href: '/settings', icon: Settings },
    { name: 'Help & Docs', href: '/help', icon: HelpCircle },
  ];

  const isActive = (path) => location.pathname === path;

  const ThemeToggle = () => (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="btn-icon"
      aria-label="Toggle theme"
    >
      {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    </button>
  );

  const SidebarContent = () => (
    <div className="flex grow flex-col gap-y-5 overflow-y-auto bg-[#1F2937] px-6 pb-4">
      {/* Logo */}
      <div className="flex h-16 shrink-0 items-center gap-x-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-brand-primary">
          <BarChart3 className="w-5 h-5 text-white" />
        </div>
        <span className="text-xl font-bold text-white">DataSage</span>
      </div>
      
      {/* Navigation */}
      <nav className="flex flex-1 flex-col">
        <ul role="list" className="flex flex-1 flex-col gap-y-7">
          <li>
            <ul role="list" className="-mx-2 space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.name}>
                    <Link
                      to={item.href}
                      onClick={() => setSidebarOpen(false)}
                      className={`group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold
                        ${isActive(item.href)
                          ? 'bg-gray-800 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-gray-800'}`
                      }
                    >
                      <Icon className="h-6 w-6 shrink-0" />
                      {item.name}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </li>
          <li className="mt-auto">
            <ul role="list" className="-mx-2 space-y-1">
              {secondaryNavigation.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.name}>
                     <Link
                      to={item.href}
                      onClick={() => setSidebarOpen(false)}
                      className={`group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold
                        ${isActive(item.href)
                          ? 'bg-gray-800 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-gray-800'}`
                      }
                    >
                      <Icon className="h-6 w-6 shrink-0" />
                      {item.name}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </li>
        </ul>
      </nav>
    </div>
  );

  return (
    <>
      {/* Mobile Sidebar */}
      <div className={`relative z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`} role="dialog" aria-modal="true">
        <div className="fixed inset-0 bg-gray-900/80" onClick={() => setSidebarOpen(false)}></div>
        <div className="fixed inset-0 flex">
          <div className="relative mr-16 flex w-full max-w-xs flex-1">
            <div className="absolute left-full top-0 flex w-16 justify-center pt-5">
              <button type="button" className="-m-2.5 p-2.5" onClick={() => setSidebarOpen(false)}>
                <X className="h-6 w-6 text-white" />
              </button>
            </div>
            <SidebarContent />
          </div>
        </div>
      </div>

      {/* Static Sidebar for Desktop */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-72 lg:flex-col">
        <SidebarContent />
      </div>

      <div className="lg:pl-72">
        {/* Top Navigation Bar */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-border-primary bg-bg-secondary px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
          <button type="button" className="-m-2.5 p-2.5 text-text-secondary lg:hidden" onClick={() => setSidebarOpen(true)}>
            <Menu className="h-6 w-6" />
          </button>

          {/* Separator */}
          <div className="h-6 w-px bg-gray-900/10 lg:hidden" aria-hidden="true" />

          <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
            {/* Search Bar */}
            <form className="relative flex flex-1" action="#" method="GET">
              <label htmlFor="search-field" className="sr-only">Search</label>
              <Search className="pointer-events-none absolute inset-y-0 left-0 h-full w-5 text-text-muted" />
              <input
                id="search-field"
                className="block h-full w-full border-0 py-0 pl-8 pr-0 text-text-primary bg-transparent placeholder:text-text-muted focus:ring-0 sm:text-sm"
                placeholder="Search projects, datasets..."
                type="search"
                name="search"
              />
            </form>

            <div className="flex items-center gap-x-4 lg:gap-x-6">
              <Link to="/datasets" className="btn btn-primary hidden sm:flex">
                <Plus className="w-4 h-4 mr-2" />
                Upload
              </Link>
              <ThemeToggle />
              <button type="button" className="btn-icon">
                <Bell className="h-6 w-6" />
              </button>

              {/* Profile dropdown */}
              <div className="relative">
                <button 
                  className="-m-1.5 flex items-center p-1.5"
                  onClick={() => setProfileOpen(!profileOpen)}
                >
                  <span className="sr-only">Open user menu</span>
                  <div className="h-8 w-8 rounded-full bg-bg-tertiary flex items-center justify-center">
                    <User className="h-5 w-5 text-text-secondary" />
                  </div>
                  <span className="hidden lg:flex lg:items-center">
                    <span className="ml-4 text-sm font-semibold leading-6 text-text-primary" aria-hidden="true">
                      {user?.username || 'User'}
                    </span>
                    <ChevronDown className="ml-2 h-5 w-5 text-text-muted" />
                  </span>
                </button>
                {profileOpen && (
                  <div 
                    className="absolute right-0 z-10 mt-2.5 w-48 origin-top-right rounded-md bg-bg-secondary py-2 shadow-lg ring-1 ring-gray-900/5 focus:outline-none"
                    role="menu" aria-orientation="vertical" tabIndex="-1"
                  >
                    <Link to="/settings" className="dropdown-item" onClick={() => setProfileOpen(false)}>
                      Your Profile
                    </Link>
                    <button onClick={logout} className="dropdown-item w-full text-left">
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main Page Content */}
        <main className="py-10">
          <div className="px-4 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>

      {/* Simple global style for dropdown items */}
      <style jsx global>{`
        .btn-icon {
          color: var(--text-secondary);
          padding: 0.5rem;
          border-radius: var(--radius-md);
          transition: background-color var(--transition-fast), color var(--transition-fast);
        }
        .btn-icon:hover {
          background-color: var(--bg-hover);
          color: var(--text-primary);
        }
        .dropdown-item {
          display: block;
          padding: 0.5rem 1rem;
          font-size: 0.875rem;
          color: var(--text-primary);
          transition: background-color var(--transition-fast);
        }
        .dropdown-item:hover {
          background-color: var(--bg-hover);
        }
      `}</style>
    </>
  );
};

export default Layout;