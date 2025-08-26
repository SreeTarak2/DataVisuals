import React from 'react'
import { 
  Upload, 
  BarChart3, 
  Brain, 
  TrendingUp,
  Database,
  Sparkles,
  ArrowRight
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { usePersona } from '../contexts/PersonaContext'

const Dashboard: React.FC = () => {
  const { persona, isNormal } = usePersona()

  const quickActions = [
    {
      title: 'Upload Dataset',
      description: 'Upload CSV or Excel files for analysis',
      icon: Upload,
      href: '/datasets',
      color: 'primary'
    },
    {
      title: 'AI Analysis',
      description: 'Get intelligent insights from your data',
      icon: Brain,
      href: '/analysis',
      color: 'accent'
    },
    {
      title: 'Dashboard Templates',
      description: 'Use pre-built dashboard layouts',
      icon: BarChart3,
      href: '/templates',
      color: 'success'
    }
  ]

  const personaInsights = {
    normal: {
      title: 'Business Insights',
      description: 'Get clear, actionable insights that help you make better business decisions.',
      features: [
        'Simple explanations in plain English',
        'Business-focused recommendations',
        'Easy-to-understand visualizations',
        'Key performance indicators'
      ]
    },
    expert: {
      title: 'Technical Analysis',
      description: 'Deep dive into statistical analysis and advanced data patterns.',
      features: [
        'Statistical significance testing',
        'Correlation analysis',
        'Anomaly detection',
        'Confidence intervals'
      ]
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold text-secondary-900 mb-4">
          Welcome to <span className="gradient-text">DataSage AI</span>
        </h1>
        <p className="text-xl text-secondary-600 max-w-3xl mx-auto">
          Transform your raw data into intelligent insights with AI-powered analysis and visualization.
          {isNormal ? ' Get clear, business-friendly explanations.' : ' Dive deep into statistical analysis and technical insights.'}
        </p>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-2xl font-semibold text-secondary-900 mb-6">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {quickActions.map((action) => (
            <Link
              key={action.title}
              to={action.href}
              className="group card p-6 hover:shadow-medium transition-all duration-200 hover:-translate-y-1"
            >
              <div className="flex items-center space-x-4">
                <div className={`p-3 rounded-lg bg-${action.color}-100 text-${action.color}-600`}>
                  <action.icon className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-secondary-900 group-hover:text-primary-600 transition-colors">
                    {action.title}
                  </h3>
                  <p className="text-sm text-secondary-600 mt-1">{action.description}</p>
                </div>
                <ArrowRight className="h-5 w-5 text-secondary-400 group-hover:text-primary-600 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Persona Insights */}
      <div>
        <h2 className="text-2xl font-semibold text-secondary-900 mb-6">
          {personaInsights[persona].title}
        </h2>
        <div className="card p-6">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-accent-100 text-accent-600">
              <Sparkles className="h-6 w-6" />
            </div>
            <div className="flex-1">
              <p className="text-secondary-700 mb-4">{personaInsights[persona].description}</p>
              <ul className="space-y-2">
                {personaInsights[persona].features.map((feature, index) => (
                  <li key={index} className="flex items-center space-x-2">
                    <div className="h-2 w-2 rounded-full bg-accent-500" />
                    <span className="text-secondary-700">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Overview */}
      <div>
        <h2 className="text-2xl font-semibold text-secondary-900 mb-6">Platform Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="card p-6 text-center">
            <div className="p-3 rounded-lg bg-primary-100 text-primary-600 mx-auto mb-3">
              <Database className="h-6 w-6" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900">0</h3>
            <p className="text-sm text-secondary-600">Datasets</p>
          </div>
          
          <div className="card p-6 text-center">
            <div className="p-3 rounded-lg bg-success-100 text-success-600 mx-auto mb-3">
              <BarChart3 className="h-6 w-6" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900">3</h3>
            <p className="text-sm text-secondary-600">Dashboard Templates</p>
          </div>
          
          <div className="card p-6 text-center">
            <div className="p-3 rounded-lg bg-accent-100 text-accent-600 mx-auto mb-3">
              <Brain className="h-6 w-6" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900">AI</h3>
            <p className="text-sm text-secondary-600">Powered Insights</p>
          </div>
          
          <div className="card p-6 text-center">
            <div className="p-3 rounded-lg bg-warning-100 text-warning-600 mx-auto mb-3">
              <TrendingUp className="h-6 w-6" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900">Real-time</h3>
            <p className="text-sm text-secondary-600">Analysis</p>
          </div>
        </div>
      </div>

      {/* Getting Started */}
      <div className="card p-8 text-center bg-gradient-to-r from-primary-50 to-accent-50 border-primary-200">
        <h2 className="text-2xl font-semibold text-secondary-900 mb-4">Ready to Get Started?</h2>
        <p className="text-secondary-600 mb-6 max-w-2xl mx-auto">
          Upload your first dataset and discover the power of AI-driven data analysis. 
          Get instant insights, visualization recommendations, and intelligent dashboards.
        </p>
        <Link
          to="/datasets"
          className="btn-primary inline-flex items-center space-x-2"
        >
          <Upload className="h-5 w-5" />
          <span>Upload Your First Dataset</span>
        </Link>
      </div>
    </div>
  )
}

export default Dashboard
