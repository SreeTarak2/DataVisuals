/**
 * RedesignLimitModal Component
 * 
 * Modal displayed when user reaches max dashboard redesign limit.
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '../../../components/common/Button';

const RedesignLimitModal = ({ isOpen, onClose, onRefresh, MAX_REDESIGNS }) => {
    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="bg-slate-800 rounded-2xl p-8 max-w-md w-full border border-slate-700 shadow-2xl"
                    >
                        <div className="flex items-center gap-4 mb-6">
                            <div className="p-3 bg-amber-500/20 rounded-full">
                                <AlertTriangle className="w-8 h-8 text-amber-400" />
                            </div>
                            <div>
                                <h3 className="text-2xl font-bold text-white">Redesign Limit Reached</h3>
                                <p className="text-slate-400 text-sm mt-1">Maximum redesigns per session</p>
                            </div>
                        </div>

                        <div className="bg-slate-900/50 rounded-lg p-4 mb-6 border border-slate-700">
                            <p className="text-slate-300 mb-3">
                                You've reached the maximum of <span className="font-bold text-emerald-400">{MAX_REDESIGNS} redesigns</span> for this dashboard session.
                            </p>
                            <p className="text-slate-400 text-sm">
                                To generate more dashboard variations:
                            </p>
                            <ul className="mt-2 space-y-2 text-sm text-slate-400">
                                <li className="flex items-start gap-2">
                                    <span className="text-emerald-400 mt-0.5">•</span>
                                    <span>Refresh the page to reset the counter</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-emerald-400 mt-0.5">•</span>
                                    <span>Upload a new dataset to start fresh</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-emerald-400 mt-0.5">•</span>
                                    <span>Use the current dashboard design</span>
                                </li>
                            </ul>
                        </div>

                        <div className="flex gap-3">
                            <Button
                                onClick={onRefresh}
                                className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                            >
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Refresh Page
                            </Button>
                            <Button
                                onClick={onClose}
                                className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-200"
                            >
                                Keep Current Design
                            </Button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

export default RedesignLimitModal;
