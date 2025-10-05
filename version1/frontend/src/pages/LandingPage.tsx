import React from 'react'
import { Link } from 'react-router-dom'
import { BarChart3, ArrowRight, Upload, Zap, Download, Sparkles } from 'lucide-react'

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="bg-black/95 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <BarChart3 className="h-5 w-5 text-black" />
              </div>
              <span className="text-2xl font-bold">DataSage</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link
                to="/login"
                className="text-gray-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/login"
                className="bg-white text-black px-6 py-2 rounded-lg font-medium hover:bg-gray-100 transition-colors"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <div className="mb-8">
            <h1 className="text-6xl md:text-7xl font-bold mb-6 leading-tight">
              AI-Powered
              <br />
              <span className="text-gray-400">Chart Generation</span>
            </h1>
          </div>
          
          <h2 className="text-3xl md:text-4xl font-light text-gray-300 mb-8 max-w-4xl mx-auto">
            Transform data into beautiful visualizations
          </h2>
          
          <p className="text-xl text-gray-400 mb-12 max-w-3xl mx-auto leading-relaxed">
            Upload CSV or Excel files and let AI generate interactive charts in seconds. 
            Export your customized visualizations for presentations, reports, and dashboards.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-6 justify-center mb-16">
            <Link
              to="/login"
              className="bg-white text-black px-8 py-4 rounded-lg font-medium hover:bg-gray-100 transition-colors inline-flex items-center justify-center text-lg"
            >
              Start Free
              <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
            <button className="border border-gray-600 text-white px-8 py-4 rounded-lg font-medium hover:bg-gray-900 transition-colors text-lg">
              Watch Demo
            </button>
          </div>

          {/* Hero Visual Placeholder */}
          <div className="relative max-w-5xl mx-auto">
            <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                <div className="space-y-4">
                  <div className="h-4 bg-gray-700 rounded w-3/4"></div>
                  <div className="h-4 bg-gray-700 rounded w-1/2"></div>
                  <div className="h-4 bg-gray-700 rounded w-2/3"></div>
                </div>
                <div className="bg-gray-800 rounded-lg h-64 flex items-center justify-center">
                  <BarChart3 className="h-16 w-16 text-gray-600" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-20">
            <h2 className="text-4xl font-bold mb-6">
              Everything you need for data visualization
            </h2>
            <p className="text-xl text-gray-400 max-w-3xl mx-auto">
              Our platform combines powerful AI with intuitive design to make data visualization accessible to everyone.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-12">
            <div className="text-center group">
              <div className="w-20 h-20 bg-white rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <Upload className="h-10 w-10 text-black" />
              </div>
              <h3 className="text-2xl font-semibold mb-4">Upload Any Dataset</h3>
              <p className="text-gray-400 text-lg leading-relaxed">
                Upload any spreadsheet. Maximum two million rows. Support for CSV, Excel, and more formats.
              </p>
            </div>

            <div className="text-center group">
              <div className="w-20 h-20 bg-white rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <Zap className="h-10 w-10 text-black" />
              </div>
              <h3 className="text-2xl font-semibold mb-4">Automatic Analysis</h3>
              <p className="text-gray-400 text-lg leading-relaxed">
                AI automatically analyzes your data and intuits the most compatible chart type for optimal visualization.
              </p>
            </div>

            <div className="text-center group">
              <div className="w-20 h-20 bg-white rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <Download className="h-10 w-10 text-black" />
              </div>
              <h3 className="text-2xl font-semibold mb-4">Export & Share</h3>
              <p className="text-gray-400 text-lg leading-relaxed">
                Export your visualizations in multiple formats. Perfect for presentations, reports, and dashboards.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <div className="bg-gray-900 rounded-3xl p-12 border border-gray-800">
            <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center mx-auto mb-8">
              <Sparkles className="h-8 w-8 text-black" />
            </div>
            <h2 className="text-4xl font-bold mb-6">
              Ready to transform your data?
            </h2>
            <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
              Join thousands of users who are already creating beautiful visualizations with AI-powered insights.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/login"
                className="bg-white text-black px-8 py-4 rounded-lg font-medium hover:bg-gray-100 transition-colors inline-flex items-center justify-center text-lg"
              >
                Get Started Free
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <button className="border border-gray-600 text-white px-8 py-4 rounded-lg font-medium hover:bg-gray-800 transition-colors text-lg">
                View Examples
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 border-t border-gray-800 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-3 mb-4 md:mb-0">
              <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
                <BarChart3 className="h-4 w-4 text-black" />
              </div>
              <span className="text-xl font-bold">DataSage</span>
            </div>
            <div className="flex items-center space-x-8 text-gray-400">
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <p className="text-gray-500">© 2025 DataSage</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage