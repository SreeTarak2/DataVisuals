import React, { useState } from 'react'
import { Settings as SettingsIcon, User, Bell, Shield, Palette, Database, Save, RefreshCw } from 'lucide-react'

const Settings = () => {
  const [activeTab, setActiveTab] = useState('profile')
  const [settings, setSettings] = useState({
    profile: {
      name: 'Admin User',
      email: 'admin@datasage.ai',
      role: 'Administrator',
      timezone: 'UTC-8'
    },
    notifications: {
      emailNotifications: true,
      pushNotifications: true,
      weeklyReports: true,
      dataAlerts: true,
      systemUpdates: false
    },
    appearance: {
      theme: 'light',
      language: 'en',
      dateFormat: 'MM/DD/YYYY',
      timeFormat: '12h'
    },
    data: {
      autoRefresh: true,
      refreshInterval: 300,
      maxFileSize: 10,
      retentionPeriod: 365
    }
  })

  const tabs = [
    { id: 'profile', name: 'Profile', icon: User },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'appearance', name: 'Appearance', icon: Palette },
    { id: 'data', name: 'Data Settings', icon: Database },
    { id: 'security', name: 'Security', icon: Shield }
  ]

  const handleSave = () => {
    console.log('Saving settings:', settings)
    // Implement save functionality
  }

  const handleReset = () => {
    console.log('Resetting settings')
    // Implement reset functionality
  }

  const renderProfileSettings = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Full Name
        </label>
        <input
          type="text"
          value={settings.profile.name}
          onChange={(e) => setSettings({
            ...settings,
            profile: { ...settings.profile, name: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Email Address
        </label>
        <input
          type="email"
          value={settings.profile.email}
          onChange={(e) => setSettings({
            ...settings,
            profile: { ...settings.profile, email: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Role
        </label>
        <select
          value={settings.profile.role}
          onChange={(e) => setSettings({
            ...settings,
            profile: { ...settings.profile, role: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="Administrator">Administrator</option>
          <option value="Analyst">Analyst</option>
          <option value="Viewer">Viewer</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Timezone
        </label>
        <select
          value={settings.profile.timezone}
          onChange={(e) => setSettings({
            ...settings,
            profile: { ...settings.profile, timezone: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="UTC-8">Pacific Time (UTC-8)</option>
          <option value="UTC-5">Eastern Time (UTC-5)</option>
          <option value="UTC+0">UTC</option>
          <option value="UTC+1">Central European Time</option>
        </select>
      </div>
    </div>
  )

  const renderNotificationSettings = () => (
    <div className="space-y-6">
      {Object.entries(settings.notifications).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-gray-900">
              {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
            </h3>
            <p className="text-sm text-gray-500">
              {key === 'emailNotifications' && 'Receive notifications via email'}
              {key === 'pushNotifications' && 'Receive push notifications in browser'}
              {key === 'weeklyReports' && 'Get weekly summary reports'}
              {key === 'dataAlerts' && 'Get alerts for data anomalies'}
              {key === 'systemUpdates' && 'Get notifications for system updates'}
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={value}
              onChange={(e) => setSettings({
                ...settings,
                notifications: { ...settings.notifications, [key]: e.target.checked }
              })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
      ))}
    </div>
  )

  const renderAppearanceSettings = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Theme
        </label>
        <div className="flex space-x-4">
          <label className="flex items-center">
            <input
              type="radio"
              name="theme"
              value="light"
              checked={settings.appearance.theme === 'light'}
              onChange={(e) => setSettings({
                ...settings,
                appearance: { ...settings.appearance, theme: e.target.value }
              })}
              className="mr-2"
            />
            Light
          </label>
          <label className="flex items-center">
            <input
              type="radio"
              name="theme"
              value="dark"
              checked={settings.appearance.theme === 'dark'}
              onChange={(e) => setSettings({
                ...settings,
                appearance: { ...settings.appearance, theme: e.target.value }
              })}
              className="mr-2"
            />
            Dark
          </label>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Language
        </label>
        <select
          value={settings.appearance.language}
          onChange={(e) => setSettings({
            ...settings,
            appearance: { ...settings.appearance, language: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="en">English</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Date Format
        </label>
        <select
          value={settings.appearance.dateFormat}
          onChange={(e) => setSettings({
            ...settings,
            appearance: { ...settings.appearance, dateFormat: e.target.value }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="MM/DD/YYYY">MM/DD/YYYY</option>
          <option value="DD/MM/YYYY">DD/MM/YYYY</option>
          <option value="YYYY-MM-DD">YYYY-MM-DD</option>
        </select>
      </div>
    </div>
  )

  const renderDataSettings = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-900">Auto Refresh</h3>
          <p className="text-sm text-gray-500">Automatically refresh data at regular intervals</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={settings.data.autoRefresh}
            onChange={(e) => setSettings({
              ...settings,
              data: { ...settings.data, autoRefresh: e.target.checked }
            })}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Refresh Interval (seconds)
        </label>
        <input
          type="number"
          value={settings.data.refreshInterval}
          onChange={(e) => setSettings({
            ...settings,
            data: { ...settings.data, refreshInterval: parseInt(e.target.value) }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Maximum File Size (MB)
        </label>
        <input
          type="number"
          value={settings.data.maxFileSize}
          onChange={(e) => setSettings({
            ...settings,
            data: { ...settings.data, maxFileSize: parseInt(e.target.value) }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Data Retention Period (days)
        </label>
        <input
          type="number"
          value={settings.data.retentionPeriod}
          onChange={(e) => setSettings({
            ...settings,
            data: { ...settings.data, retentionPeriod: parseInt(e.target.value) }
          })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
    </div>
  )

  const renderSecuritySettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-2">Change Password</h3>
        <div className="space-y-4">
          <input
            type="password"
            placeholder="Current password"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <input
            type="password"
            placeholder="New password"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <input
            type="password"
            placeholder="Confirm new password"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-2">Two-Factor Authentication</h3>
        <p className="text-sm text-gray-500 mb-4">
          Add an extra layer of security to your account
        </p>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Enable 2FA
        </button>
      </div>
    </div>
  )

  const renderTabContent = () => {
    switch (activeTab) {
      case 'profile':
        return renderProfileSettings()
      case 'notifications':
        return renderNotificationSettings()
      case 'appearance':
        return renderAppearanceSettings()
      case 'data':
        return renderDataSettings()
      case 'security':
        return renderSecuritySettings()
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-600 mt-1">
            Manage your account and application preferences
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleReset}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Reset</span>
          </button>
          <button
            onClick={handleSave}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Save className="w-4 h-4" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar */}
        <div className="lg:w-64">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2 text-left rounded-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                <span>{tab.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            {renderTabContent()}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings



