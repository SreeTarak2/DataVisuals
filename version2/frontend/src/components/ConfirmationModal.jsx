import React from 'react'
import { AlertTriangle, X } from 'lucide-react'

/**
 * Reusable Confirmation Modal Component
 * 
 * Usage example:
 * <ConfirmationModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onConfirm={handleConfirm}
 *   title="Delete Item"
 *   message="Are you sure you want to delete this item?"
 *   confirmText="Delete"
 *   cancelText="Cancel"
 *   type="danger" // "danger", "warning", "info"
 * />
 */
const ConfirmationModal = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  title = "Confirm Action", 
  message = "Are you sure you want to proceed?", 
  confirmText = "Confirm", 
  cancelText = "Cancel",
  type = "danger" // "danger", "warning", "info"
}) => {
  if (!isOpen) return null

  const getTypeStyles = () => {
    switch (type) {
      case 'danger':
        return {
          icon: 'text-red-600',
          iconBg: 'bg-red-100',
          confirmBtn: 'bg-red-600 hover:bg-red-700 text-white',
          border: 'border-red-200'
        }
      case 'warning':
        return {
          icon: 'text-yellow-600',
          iconBg: 'bg-yellow-100',
          confirmBtn: 'bg-yellow-600 hover:bg-yellow-700 text-white',
          border: 'border-yellow-200'
        }
      case 'info':
        return {
          icon: 'text-blue-600',
          iconBg: 'bg-blue-100',
          confirmBtn: 'bg-blue-600 hover:bg-blue-700 text-white',
          border: 'border-blue-200'
        }
      default:
        return {
          icon: 'text-gray-600',
          iconBg: 'bg-gray-100',
          confirmBtn: 'bg-gray-600 hover:bg-gray-700 text-white',
          border: 'border-gray-200'
        }
    }
  }

  const styles = getTypeStyles()

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md transform transition-all">
        {/* Header */}
        <div className={`flex items-center justify-between p-6 border-b ${styles.border}`}>
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-full ${styles.iconBg}`}>
              <AlertTriangle className={`w-5 h-5 ${styles.icon}`} />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          <p className="text-gray-600 leading-relaxed">{message}</p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-6 bg-gray-50 rounded-b-lg">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors ${styles.confirmBtn}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmationModal



