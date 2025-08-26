import React, { useState } from 'react'
import { LayoutTemplate, BarChart3, TrendingUp, Search, Play, Eye, Settings } from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'

interface DashboardTemplate {
  id: string
  name: string
  description: string
  type: string
  icon: React.ComponentType<any>
  color: string
  features: string[]
  personaFeatures: {
    normal: string[]
    expert: string[]
  }
}

const Templates: React.FC = () => {
  const { persona, isNormal } = usePersona()
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)

  const templates: DashboardTemplate[] = [
    {
      id: 'kpi',
      name: 'KPI Dashboard',
      description: 'Key performance indicators and metrics overview',
      type: 'kpi',
      icon: BarChart3,
      color: 'primary',
      features: ['Metrics cards', 'Trend charts', 'Comparison views', 'Real-time updates'],
      personaFeatures: {
        normal: ['Business metrics', 'Simple KPIs', 'Goal tracking', 'Performance overview'],
        expert: ['Statistical significance', 'Confidence intervals', 'Trend analysis', 'Anomaly detection']
      }
    },
    {
      id: 'exploration',
      name: 'Data Exploration',
      description: 'Interactive data exploration and analysis',
      type: 'exploration',
      icon: Search,
      color: 'success',
      features: ['Correlation analysis', 'Distribution charts', 'Outlier detection', 'Interactive filters'],
      personaFeatures: {
        normal: ['Easy data browsing', 'Simple insights', 'Quick comparisons', 'Visual patterns'],
        expert: ['Statistical testing', 'Advanced correlations', 'Multivariate analysis', 'Hypothesis testing']
      }
    },
    {
      id: 'forecast',
      name: 'Forecasting Dashboard',
      description: 'Time series analysis and predictions',
      type: 'forecast',
      icon: TrendingUp,
      color: 'accent',
      features: ['Historical trends', 'Forecast models', 'Seasonal patterns', 'Prediction intervals'],
      personaFeatures: {
        normal: ['Future trends', 'Seasonal insights', 'Growth projections', 'Business planning'],
        expert: ['Model parameters', 'Confidence intervals', 'Statistical validation', 'Model comparison']
      }
    }
  ]

  const getTemplateIcon = (template: DashboardTemplate) => {
    const IconComponent = template.icon
    return (
      <div className={`p-4 rounded-lg bg-${template.color}-100 text-${template.color}-600`}>
        <IconComponent className="h-8 w-8" />
      </div>
    )
  }

  const getTemplateColor = (template: DashboardTemplate) => {
    return template.color
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 mb-2">Dashboard Templates</h1>
        <p className="text-secondary-600">
          {isNormal
            ? 'Choose from pre-built dashboard layouts designed for business users with clear insights and actionable metrics.'
            : 'Advanced dashboard templates with statistical depth, technical analysis, and comprehensive data exploration capabilities.'
          }
        </p>
      </div>

      {/* Template Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {templates.map((template) => (
          <div key={template.id} className="card p-6 hover:shadow-medium transition-all duration-200">
            <div className="flex items-center space-x-4 mb-4">
              {getTemplateIcon(template)}
              <div>
                <h3 className="text-xl font-semibold text-secondary-900">{template.name}</h3>
                <p className="text-sm text-secondary-600">{template.type}</p>
              </div>
            </div>
            
            <p className="text-secondary-700 mb-6">{template.description}</p>
            
            <div className="space-y-4 mb-6">
              <div>
                <h4 className="font-medium text-secondary-900 mb-2">Core Features</h4>
                <ul className="space-y-1">
                  {template.features.map((feature, index) => (
                    <li key={index} className="flex items-center space-x-2 text-sm text-secondary-600">
                      <div className="h-1.5 w-1.5 rounded-full bg-secondary-400" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div>
                <h4 className="font-medium text-secondary-900 mb-2">
                  {isNormal ? 'Business Features' : 'Expert Features'}
                </h4>
                <ul className="space-y-1">
                  {template.personaFeatures[persona].map((feature, index) => (
                    <li key={index} className="flex items-center space-x-2 text-sm text-secondary-600">
                      <div className={`h-1.5 w-1.5 rounded-full bg-${getTemplateColor(template)}-500`} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            
            <div className="flex space-x-2">
              <button className="btn-outline flex-1 text-sm">
                <Eye className="h-4 w-4 mr-2" />
                Preview
              </button>
              <button 
                className="btn-primary flex-1 text-sm"
                onClick={() => setSelectedTemplate(template.id)}
              >
                <Play className="h-4 w-4 mr-2" />
                Use Template
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Template Details Modal */}
      {selectedTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50" onClick={() => setSelectedTemplate(null)} />
          <div className="relative bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-secondary-900">
                  {templates.find(t => t.id === selectedTemplate)?.name}
                </h2>
                <button
                  onClick={() => setSelectedTemplate(null)}
                  className="p-2 text-secondary-400 hover:text-secondary-600 rounded-lg"
                >
                  <Settings className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold text-secondary-900 mb-3">Template Configuration</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <label className="block text-sm font-medium text-secondary-700">
                        Dashboard Name
                      </label>
                      <input
                        type="text"
                        placeholder="Enter dashboard name"
                        className="input"
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="block text-sm font-medium text-secondary-700">
                        Dataset
                      </label>
                      <select className="input">
                        <option>Select a dataset</option>
                        <option>Sales Data</option>
                        <option>Customer Data</option>
                        <option>Product Data</option>
                      </select>
                    </div>
                  </div>
                </div>
                
                <div>
                  <h3 className="font-semibold text-secondary-900 mb-3">Layout Preview</h3>
                  <div className="bg-secondary-50 rounded-lg p-4 border border-secondary-200">
                    <div className="grid grid-cols-12 gap-2 h-32">
                      <div className="col-span-3 bg-primary-200 rounded flex items-center justify-center text-xs text-primary-800">
                        KPI Card
                      </div>
                      <div className="col-span-9 bg-success-200 rounded flex items-center justify-center text-xs text-success-800">
                        Main Chart
                      </div>
                      <div className="col-span-6 bg-warning-200 rounded flex items-center justify-center text-xs text-warning-800">
                        Secondary Chart
                      </div>
                      <div className="col-span-6 bg-accent-200 rounded flex items-center justify-center text-xs text-accent-800">
                        Third Chart
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={() => setSelectedTemplate(null)}
                    className="btn-outline flex-1"
                  >
                    Cancel
                  </button>
                  <button className="btn-primary flex-1">
                    <Play className="h-4 w-4 mr-2" />
                    Create Dashboard
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Custom Template */}
      <div className="card p-8 text-center bg-gradient-to-r from-secondary-50 to-primary-50 border-secondary-200">
        <div className="p-4 rounded-full bg-secondary-100 mx-auto mb-4 w-20 h-20 flex items-center justify-center">
          <LayoutTemplate className="h-10 w-10 text-secondary-600" />
        </div>
        <h3 className="text-xl font-semibold text-secondary-900 mb-2">Need a Custom Template?</h3>
        <p className="text-secondary-600 mb-6 max-w-md mx-auto">
          {isNormal
            ? 'Our AI can help you create a custom dashboard layout tailored to your specific business needs.'
            : 'Create advanced custom dashboards with statistical analysis, custom visualizations, and specialized metrics.'
          }
        </p>
        <button className="btn-primary">
          <Settings className="h-5 w-5 mr-2" />
          Create Custom Template
        </button>
      </div>
    </div>
  )
}

export default Templates
