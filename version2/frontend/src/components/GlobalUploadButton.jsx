import React, { useState } from 'react'
import { FolderPlus } from 'lucide-react'
import CreateProjectModal from './features/projects/CreateProjectModal'

const GlobalUploadButton = ({ className = '', variant = 'default' }) => {
  const [isModalOpen, setIsModalOpen] = useState(false)

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
        <FolderPlus className="w-4 h-4" />
        New project
      </button>

      {isModalOpen && (
        <CreateProjectModal
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </>
  )
}

export default GlobalUploadButton
