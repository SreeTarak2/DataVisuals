import React from 'react'
import { Link } from 'react-router-dom'
import { Home, ArrowLeft, Search } from 'lucide-react'

const NotFound: React.FC = () => {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center space-y-6">
        <div className="space-y-4">
          <div className="text-8xl font-bold text-primary-200">404</div>
          <h1 className="text-3xl font-bold text-secondary-900">Page Not Found</h1>
          <p className="text-secondary-600 max-w-md mx-auto">
            Sorry, we couldn't find the page you're looking for. It might have been moved, deleted, or you entered the wrong URL.
          </p>
        </div>
        
        <div className="flex items-center justify-center space-x-4">
          <Link
            to="/"
            className="btn-primary inline-flex items-center space-x-2"
          >
            <Home className="h-5 w-5" />
            <span>Go Home</span>
          </Link>
          
          <button
            onClick={() => window.history.back()}
            className="btn-outline inline-flex items-center space-x-2"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Go Back</span>
          </button>
        </div>
        
        <div className="pt-8">
          <p className="text-sm text-secondary-500 mb-4">Or try one of these pages:</p>
          <div className="flex items-center justify-center space-x-6">
            <Link
              to="/datasets"
              className="text-primary-600 hover:text-primary-700 font-medium hover:underline"
            >
              Datasets
            </Link>
            <Link
              to="/analysis"
              className="text-primary-600 hover:text-primary-700 font-medium hover:underline"
            >
              Analysis
            </Link>
            <Link
              to="/charts"
              className="text-primary-600 hover:text-primary-700 font-medium hover:underline"
            >
              Charts
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NotFound
