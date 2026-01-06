/**
 * LoadingState Component
 * 
 * Loading spinner displayed while dashboard data is being fetched.
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

const LoadingState = () => {
    return (
        <div className="min-h-screen bg-slate-950 p-6 flex items-center justify-center">
            <div className="text-center">
                <Loader2 className="w-12 h-12 animate-spin text-blue-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Loading Dashboard</h3>
                <p className="text-slate-400">AI is analyzing your data and generating insights...</p>
            </div>
        </div>
    );
};

export default LoadingState;
