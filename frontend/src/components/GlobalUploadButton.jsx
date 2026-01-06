import React, { useState } from 'react'
import { Upload } from 'lucide-react'
import UploadModal from './UploadModal'
import useDatasetStore from '../store/datasetStore'

const GlobalUploadButton = ({ className = '', variant = 'default' }) => {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const { fetchDatasets } = useDatasetStore()

  const handleUploadSuccess = (newDataset) => {
    // Refresh the datasets list
    fetchDatasets()
    setIsModalOpen(false)
  }

  const buttonVariants = {
    default: "bg-blue-500 hover:bg-blue-600 text-white",
    ghost: "bg-slate-800/50 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600",
    outline: "bg-transparent hover:bg-slate-800 text-slate-200 border border-slate-600 hover:border-slate-500"
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200 hover:shadow-lg hover:scale-105 ${buttonVariants[variant]} ${className}`}
      >
        <Upload className="w-4 h-4" />
        Upload Data
      </button>

      <UploadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />
    </>
  )
}

export default GlobalUploadButton


