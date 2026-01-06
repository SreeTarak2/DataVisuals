/**
 * EmptyStates Component
 * 
 * Handles various empty states for the dashboard:
 * - No dataset selected
 * - Empty dataset (0 rows/columns)
 * - Dataset still processing
 * 
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { Database, AlertTriangle, Upload } from 'lucide-react';
import { Button } from '../../../components/Button';

const EmptyStates = ({ type, selectedDataset, onUpload, onNavigateToDatasets }) => {
    if (type === 'no-dataset') {
        return (
            <div className="text-center py-20 bg-slate-800/50 border border-slate-700 rounded-xl">
                <Database className="w-16 h-16 mx-auto text-slate-500 mb-6" />
                <h3 className="text-2xl font-semibold text-white mb-3">No Data Has Been Uploaded</h3>
                <p className="text-slate-400 mb-8 max-w-md mx-auto">
                    Upload your first dataset to begin your AI-powered data exploration journey.
                    Our intelligent system will automatically analyze and create beautiful visualizations for you.
                </p>
                <Button
                    onClick={onUpload}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 text-lg"
                >
                    <Upload className="w-5 h-5 mr-2" />
                    Upload Your First Dataset
                </Button>
            </div>
        );
    }

    if (type === 'empty-dataset') {
        return (
            <div className="text-center py-20 bg-red-900/20 border-2 border-red-500/50 rounded-xl">
                <AlertTriangle className="w-16 h-16 mx-auto text-red-400 mb-6" />
                <h3 className="text-2xl font-semibold text-white mb-3">Dataset is Empty</h3>
                <p className="text-slate-400 mb-4 max-w-md mx-auto">
                    This dataset has <span className="text-red-400 font-bold">{selectedDataset.row_count || 0} rows</span> and{' '}
                    <span className="text-red-400 font-bold">{selectedDataset.column_count || 0} columns</span>.
                </p>
                <p className="text-slate-400 mb-8 max-w-md mx-auto">
                    Please upload a valid CSV file with actual data or check if the file was processed correctly.
                </p>
                <div className="flex gap-4 justify-center">
                    <Button
                        onClick={onUpload}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3"
                    >
                        <Upload className="w-5 h-5 mr-2" />
                        Upload New Dataset
                    </Button>
                    <Button
                        onClick={onNavigateToDatasets}
                        className="bg-slate-700 hover:bg-slate-600 text-white px-6 py-3"
                    >
                        <Database className="w-5 h-5 mr-2" />
                        View All Datasets
                    </Button>
                </div>
            </div>
        );
    }

    return null;
};

export default EmptyStates;
