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
                        className="rounded-2xl p-8 max-w-md w-full border shadow-2xl"
                        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                    >
                        <div className="flex items-center gap-4 mb-6">
                            <div className="p-3 rounded-full" style={{ background: 'var(--accent-warning)', opacity: 0.15 }}>
                                <AlertTriangle className="w-8 h-8" style={{ color: 'var(--accent-warning)' }} />
                            </div>
                            <div>
                                <h3 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Redesign Limit Reached</h3>
                                <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Maximum redesigns per session</p>
                            </div>
                        </div>

                        <div className="rounded-lg p-4 mb-6 border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                            <p className="mb-3" style={{ color: 'var(--text-primary)' }}>
                                You've reached the maximum of <span className="font-bold" style={{ color: 'var(--accent-success)' }}>{MAX_REDESIGNS} redesigns</span> for this dashboard session.
                            </p>
                            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                To generate more dashboard variations:
                            </p>
                            <ul className="mt-2 space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                <li className="flex items-start gap-2">
                                    <span className="mt-0.5" style={{ color: 'var(--accent-success)' }}>•</span>
                                    <span>Refresh the page to reset the counter</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="mt-0.5" style={{ color: 'var(--accent-success)' }}>•</span>
                                    <span>Upload a new dataset to start fresh</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="mt-0.5" style={{ color: 'var(--accent-success)' }}>•</span>
                                    <span>Use the current dashboard design</span>
                                </li>
                            </ul>
                        </div>

                        <div className="flex gap-3">
                            <Button
                                onClick={onRefresh}
                                style={{ background: 'var(--accent-success)' }}
                                className="flex-1 text-white hover:opacity-90"
                            >
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Refresh Page
                            </Button>
                            <Button
                                onClick={onClose}
                                style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                                className="flex-1 hover:opacity-80"
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
