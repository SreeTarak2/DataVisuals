import React from 'react'
import { Link } from 'react-router-dom'
import { 
  BarChart3, 
  Brain, 
  Database, 
  Zap, 
  Shield, 
  ArrowRight, 
  CheckCircle,
  Play,
  Star,
  Users,
  TrendingUp,
  FileText,
  PieChart,
  LineChart
} from 'lucide-react'

const LandingPage = () => {
  const features = [
    {
      icon: Brain,
      title: "AI-Powered Analysis",
      description: "Intelligent data analysis with machine learning algorithms that automatically detect patterns and generate insights."
    },
    {
      icon: BarChart3,
      title: "Smart Visualizations",
      description: "Automatically recommend the best chart types based on your data structure and analysis goals."
    },
    {
      icon: Database,
      title: "Multi-Format Support",
      description: "Upload and analyze data from CSV, Excel, and JSON files with seamless processing."
    },
    {
      icon: Zap,
      title: "Real-time Processing",
      description: "Fast data processing with optimized algorithms for handling large datasets efficiently."
    },
    {
      icon: Shield,
      title: "Secure & Private",
      description: "Your data stays secure with enterprise-grade encryption and privacy protection."
    },
    {
      icon: TrendingUp,
      title: "Advanced Analytics",
      description: "Deep statistical analysis with trend detection, anomaly identification, and predictive insights."
    }
  ]

  const capabilities = [
    "Automatic data profiling and quality assessment",
    "Intelligent chart type recommendations",
    "Statistical analysis and trend detection",
    "Interactive drill-down capabilities",
    "Export visualizations in multiple formats",
    "Collaborative dashboard sharing",
    "Real-time data processing",
    "Custom visualization templates"
  ]

  const chartTypes = [
    { icon: BarChart3, name: "Bar Charts", color: "text-blue-400" },
    { icon: LineChart, name: "Line Charts", color: "text-green-400" },
    { icon: PieChart, name: "Pie Charts", color: "text-purple-400" },
    { icon: TrendingUp, name: "Trend Analysis", color: "text-orange-400" }
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Navigation */}
      <nav className="bg-gray-900/95 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">DataSage AI</span>
            </div>
            <div className="hidden md:flex items-center space-x-8">
              <a href="#features" className="text-gray-300 hover:text-white transition-colors">Features</a>
              <a href="#capabilities" className="text-gray-300 hover:text-white transition-colors">Capabilities</a>
              <a href="#pricing" className="text-gray-300 hover:text-white transition-colors">Pricing</a>
              <Link 
                to="/register" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-purple-900/20 to-gray-900"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              Transform Your Data Into
              <span className="block bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                Intelligent Insights
              </span>
            </h1>
            <p className="text-xl text-gray-300 mb-8 max-w-3xl mx-auto">
              DataSage AI is your intelligent companion for data analysis. Upload your datasets, 
              and let our AI automatically generate insights, recommend visualizations, and 
              uncover hidden patterns in your data.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link 
                to="/register" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg text-lg font-semibold transition-colors flex items-center justify-center space-x-2"
              >
                <span>Start Analyzing</span>
                <ArrowRight className="w-5 h-5" />
              </Link>
              <button className="border border-gray-600 hover:border-gray-500 text-white px-8 py-4 rounded-lg text-lg font-semibold transition-colors flex items-center justify-center space-x-2">
                <Play className="w-5 h-5" />
                <span>Watch Demo</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Powerful AI-Driven Features
            </h2>
            <p className="text-xl text-gray-300 max-w-2xl mx-auto">
              Everything you need to analyze, visualize, and understand your data with the power of artificial intelligence.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <div key={index} className="bg-gray-800/50 p-6 rounded-xl border border-gray-700 hover:border-gray-600 transition-colors">
                <div className="w-12 h-12 bg-blue-600/20 rounded-lg flex items-center justify-center mb-4">
                  <feature.icon className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-300">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Capabilities Section */}
      <section id="capabilities" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
                What You Can Do
              </h2>
              <p className="text-xl text-gray-300 mb-8">
                DataSage AI provides comprehensive data analysis capabilities that adapt to your specific needs and data types.
              </p>
              <div className="space-y-4">
                {capabilities.map((capability, index) => (
                  <div key={index} className="flex items-start space-x-3">
                    <CheckCircle className="w-6 h-6 text-green-400 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-300">{capability}</span>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-6">
              {chartTypes.map((chart, index) => (
                <div key={index} className="bg-gray-800/50 p-6 rounded-xl border border-gray-700 text-center">
                  <chart.icon className={`w-8 h-8 ${chart.color} mx-auto mb-3`} />
                  <h3 className="text-white font-semibold">{chart.name}</h3>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              How It Works
            </h2>
            <p className="text-xl text-gray-300">
              Get started with DataSage AI in three simple steps
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6">
                <FileText className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-4">1. Upload Your Data</h3>
              <p className="text-gray-300">
                Upload CSV, Excel, or JSON files. Our system automatically detects data types and structure.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6">
                <Brain className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-4">2. AI Analysis</h3>
              <p className="text-gray-300">
                Our AI analyzes your data, identifies patterns, and recommends the best visualization approaches.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6">
                <BarChart3 className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-4">3. Generate Insights</h3>
              <p className="text-gray-300">
                Get interactive visualizations, statistical insights, and actionable recommendations.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
            Ready to Transform Your Data?
          </h2>
          <p className="text-xl text-gray-300 mb-8">
            Join thousands of users who are already using DataSage AI to make data-driven decisions.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              to="/register" 
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg text-lg font-semibold transition-colors"
            >
              Start Your Free Trial
            </Link>
            <button className="border border-gray-600 hover:border-gray-500 text-white px-8 py-4 rounded-lg text-lg font-semibold transition-colors">
              Contact Sales
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 border-t border-gray-800 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold text-white">DataSage AI</span>
              </div>
              <p className="text-gray-400">
                AI-powered data visualization and analysis platform for modern businesses.
              </p>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Product</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Documentation</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Company</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Support</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">Help Center</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Community</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Status</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Security</a></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2024 DataSage AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage

