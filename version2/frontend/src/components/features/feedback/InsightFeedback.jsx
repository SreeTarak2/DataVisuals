/**
 * InsightFeedback Component
 * =========================
 * Standard thumbs-up / thumbs-down feedback for AI responses.
 *
 * - 👍 Thumbs Up → POST /api/insights/accept (stores in ChromaDB, no alpha change)
 * - 👎 Thumbs Down → inline reason picker → POST /api/insights/reject (quality signal)
 *
 * The "Already knew" / dismiss signal for SND personalization has been moved
 * to a separate [x] dismiss button on the ChatMessage component. These two
 * concerns (response quality vs. personalization) should never have been mixed.
 *
 * Variants:
 *  - compact : Icon-only pill buttons with CSS tooltips (for dense cards)
 *  - inline  : Icons with text labels (for narrative sections)
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ThumbsUp,
    ThumbsDown,
    Check,
    Loader2,
    SendHorizonal,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { insightAPI } from '@/services/api';

const MotionDiv = motion.div;
const MotionButton = motion.button;

// ── Rejection reasons ─────────────────────────────────────────────────────
const REJECT_REASONS = [
    { value: 'inaccurate', label: 'Inaccurate or incorrect' },
    { value: 'not_helpful', label: 'Not helpful or irrelevant' },
    { value: 'missing_context', label: 'Missing context or detail' },
    { value: 'other', label: 'Other' },
];

// ── Spring config for micro-interactions ──────────────────────────────────
const springConfig = { type: 'spring', stiffness: 420, damping: 22 };

// ── Component ─────────────────────────────────────────────────────────────
const InsightFeedback = ({
    insightText,
    datasetId = null,
    variant = 'compact',
    className = '',
}) => {
    const [selected, setSelected] = useState(null); // 'up' | 'down' | null
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [confirmed, setConfirmed] = useState(false);
    const [showReasons, setShowReasons] = useState(false);
    const [selectedReason, setSelectedReason] = useState(null);
    const [customReason, setCustomReason] = useState('');

    const reasonsRef = useRef(null);

    // Close reason picker on click outside — resets both showReasons AND selected
    // to prevent the bug where buttons remain disabled after clicking away.
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (reasonsRef.current && !reasonsRef.current.contains(e.target)) {
                setShowReasons(false);
                setSelected(null);
            }
        };
        if (showReasons) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showReasons]);

    // ── Submit thumbs up ───────────────────────────────────────────────────
    const handleThumbsUp = useCallback(async () => {
        if (selected || isSubmitting) return;

        setSelected('up');
        setIsSubmitting(true);

        try {
            await insightAPI.accept({
                insightText: insightText,
                datasetId: datasetId,
            });
            setConfirmed(true);
            toast.success('Thanks for the feedback', {
                duration: 2000,
                style: {
                    background: '#0f172a',
                    color: '#e2e8f0',
                    fontSize: '15px',
                },
                iconTheme: { primary: '#10b981', secondary: '#0f172a' },
            });
        } catch (error) {
            console.error('Feedback submission failed:', error);
            toast.error('Could not save feedback');
            setSelected(null);
        } finally {
            setIsSubmitting(false);
        }
    }, [insightText, datasetId, selected, isSubmitting]);

    // ── Show reason picker on thumbs down ──────────────────────────────────
    const handleThumbsDown = useCallback(() => {
        if (selected || isSubmitting) return;
        setSelected('down');
        setShowReasons(true);
    }, [selected, isSubmitting]);

    // ── Submit thumbs down with reason ─────────────────────────────────────
    const handleSubmitRejection = useCallback(async () => {
        const reason = selectedReason === 'other'
            ? customReason.trim()
            : REJECT_REASONS.find((r) => r.value === selectedReason)?.label || null;

        if (!reason) {
            // No reason selected — just close the picker and revert
            setSelected(null);
            setShowReasons(false);
            return;
        }

        setIsSubmitting(true);

        try {
            await insightAPI.reject({
                insightText: insightText,
                datasetId: datasetId,
                reason: reason,
            });
            setConfirmed(true);
            setShowReasons(false);
            toast.success('Feedback recorded', {
                duration: 2000,
                style: {
                    background: '#0f172a',
                    color: '#e2e8f0',
                    fontSize: '15px',
                },
                iconTheme: { primary: '#f59e0b', secondary: '#0f172a' },
            });
        } catch (error) {
            console.error('Feedback submission failed:', error);
            toast.error('Could not save feedback');
            setSelected(null);
        } finally {
            setIsSubmitting(false);
        }
    }, [insightText, datasetId, selectedReason, customReason, isSubmitting]);

    // ── Cancel reason picker ───────────────────────────────────────────────
    const handleCancelRejection = useCallback(() => {
        setSelected(null);
        setShowReasons(false);
        setSelectedReason(null);
        setCustomReason('');
    }, []);

    const isCompact = variant === 'compact';

    // ── Confirmed state ────────────────────────────────────────────────────
    if (confirmed) {
        const isUp = selected === 'up';
        return (
            <MotionDiv
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={springConfig}
                className={`flex items-center ${className}`}
            >
                <div className={`flex items-center ${isCompact ? 'gap-2' : 'gap-2.5'} ${isUp ? 'text-emerald-400' : 'text-amber-400'}`}>
                    <Check className={`${isCompact ? 'w-4 h-4' : 'w-4.5 h-4.5'}`} />
                    <span className={`font-medium ${isCompact ? 'text-xs text-slate-200' : 'text-[11px]'}`}>
                        {isCompact ? 'Saved' : (isUp ? 'Marked as helpful' : 'Feedback recorded')}
                    </span>
                </div>
            </MotionDiv>
        );
    }

    // ── Default state: thumbs up / down buttons ───────────────────────────
    return (
        <div className={`relative ${className}`}>
            <div
                className={`flex items-center ${isCompact ? 'gap-1' : 'gap-3'}`}
                role="group"
                aria-label="Rate this response"
            >
                {/* Thumbs Up */}
                <div className="group/fb relative">
                    <MotionButton
                        onClick={handleThumbsUp}
                        disabled={!!selected || isSubmitting}
                        aria-label="This was helpful"
                        title="Helpful"
                        animate={{
                            opacity: selected && selected !== 'up' ? 0.25 : 1,
                            scale: selected === 'up' ? 1.12 : 1,
                        }}
                        whileHover={!selected ? { scale: 1.15, y: -1 } : {}}
                        whileTap={!selected ? { scale: 0.92 } : {}}
                        transition={springConfig}
                        className={`
                            relative flex items-center gap-1 rounded-md
                            transition-colors duration-150
                            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean/60
                            ${isCompact ? 'p-1' : 'px-1 py-0.5'}
                            ${selected === 'up'
                                ? 'text-emerald-400'
                                : 'text-zinc-500 hover:text-emerald-400 hover:bg-zinc-800/60'
                            }
                            ${selected && selected !== 'up' ? 'pointer-events-none' : 'cursor-pointer'}
                        `}
                    >
                        {selected === 'up' && isSubmitting ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                        ) : (
                            <ThumbsUp className={`${isCompact ? 'w-3.5 h-3.5' : 'w-5 h-5'}`} />
                        )}
                        {!isCompact && (
                            <span className="text-[11px] font-medium select-none">Helpful</span>
                        )}
                    </MotionButton>
                    {isCompact && !selected && (
                        <span
                            className="
                                absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                                px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap
                                bg-[#111827] text-slate-100 border border-slate-500/70
                                opacity-0 group-hover/fb:opacity-100 pointer-events-none
                                transition-opacity duration-200 z-[120]
                                shadow-2xl shadow-black/60
                                before:absolute before:top-full before:left-1/2 before:-translate-x-1/2
                                before:border-[5px] before:border-transparent before:border-t-[#111827]
                            "
                            aria-hidden="true"
                        >
                            Helpful
                        </span>
                    )}
                </div>

                {/* Thumbs Down */}
                <div className="group/fb relative">
                    <MotionButton
                        onClick={handleThumbsDown}
                        disabled={!!selected || isSubmitting}
                        aria-label="This was not helpful"
                        title="Not helpful"
                        animate={{
                            opacity: selected && selected !== 'down' ? 0.25 : 1,
                            scale: selected === 'down' && !showReasons ? 1.12 : 1,
                        }}
                        whileHover={!selected ? { scale: 1.15, y: -1 } : {}}
                        whileTap={!selected ? { scale: 0.92 } : {}}
                        transition={springConfig}
                        className={`
                            relative flex items-center gap-1 rounded-md
                            transition-colors duration-150
                            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean/60
                            ${isCompact ? 'p-1' : 'px-1 py-0.5'}
                            ${selected === 'down'
                                ? 'text-amber-400'
                                : 'text-zinc-500 hover:text-amber-400 hover:bg-zinc-800/60'
                            }
                            ${selected && selected !== 'down' ? 'pointer-events-none' : 'cursor-pointer'}
                        `}
                    >
                        {selected === 'down' && isSubmitting && !showReasons ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                        ) : (
                            <ThumbsDown className={`${isCompact ? 'w-3.5 h-3.5' : 'w-5 h-5'}`} />
                        )}
                        {!isCompact && (
                            <span className="text-[11px] font-medium select-none">Not helpful</span>
                        )}
                    </MotionButton>
                    {isCompact && !selected && (
                        <span
                            className="
                                absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                                px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap
                                bg-[#111827] text-slate-100 border border-slate-500/70
                                opacity-0 group-hover/fb:opacity-100 pointer-events-none
                                transition-opacity duration-200 z-[120]
                                shadow-2xl shadow-black/60
                                before:absolute before:top-full before:left-1/2 before:-translate-x-1/2
                                before:border-[5px] before:border-transparent before:border-t-[#111827]
                            "
                            aria-hidden="true"
                        >
                            Not helpful
                        </span>
                    )}
                </div>
            </div>

            {/* ── Reason picker (appears below thumbs down) ── */}
            <AnimatePresence>
                {showReasons && (
                    <MotionDiv
                        ref={reasonsRef}
                        initial={{ opacity: 0, y: -4, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -4, scale: 0.96 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                        className="
                            absolute top-full left-0 mt-2 z-[130] min-w-[220px]
                            bg-[#111827] border border-slate-600/50 rounded-lg
                            shadow-2xl shadow-black/50 p-3
                        "
                    >
                        <p className="text-[11px] font-semibold text-slate-300 mb-2.5 tracking-wide uppercase">
                            What's wrong?
                        </p>
                        <div className="flex flex-col gap-1">
                            {REJECT_REASONS.map((reason) => (
                                <button
                                    key={reason.value}
                                    onClick={() => setSelectedReason(reason.value)}
                                    className={`
                                        flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs
                                        transition-colors duration-100 text-left
                                        ${selectedReason === reason.value
                                            ? 'bg-ocean/15 text-ocean'
                                            : 'text-slate-300 hover:bg-white/5'
                                        }
                                    `}
                                >
                                    <span className={`
                                        w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0
                                        ${selectedReason === reason.value
                                            ? 'border-ocean bg-ocean/20'
                                            : 'border-slate-500'
                                        }
                                    `}>
                                        {selectedReason === reason.value && (
                                            <span className="w-1.5 h-1.5 rounded-full bg-ocean" />
                                        )}
                                    </span>
                                    {reason.label}
                                </button>
                            ))}
                        </div>

                        {/* Custom reason input */}
                        {selectedReason === 'other' && (
                            <div className="mt-2.5">
                                <input
                                    type="text"
                                    value={customReason}
                                    onChange={(e) => setCustomReason(e.target.value)}
                                    placeholder="Tell us more..."
                                    className="
                                        w-full px-2.5 py-1.5 rounded-md text-xs
                                        bg-white/5 border border-slate-600/50
                                        text-slate-200 placeholder-slate-500
                                        focus:outline-none focus:border-ocean/50
                                        transition-colors duration-100
                                    "
                                    autoFocus
                                />
                            </div>
                        )}

                        {/* Action buttons */}
                        <div className="flex items-center justify-end gap-2 mt-3 pt-2 border-t border-slate-700/40">
                            <button
                                onClick={handleCancelRejection}
                                className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-1 rounded transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSubmitRejection}
                                disabled={isSubmitting || (selectedReason === 'other' && !customReason.trim())}
                                className="
                                    flex items-center gap-1.5 text-[11px] font-medium
                                    bg-ocean/20 text-ocean hover:bg-ocean/30
                                    px-2.5 py-1 rounded-md transition-colors
                                    disabled:opacity-40 disabled:cursor-not-allowed
                                "
                            >
                                {isSubmitting ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                    <SendHorizonal className="w-3.5 h-3.5" />
                                )}
                                Send
                            </button>
                        </div>
                    </MotionDiv>
                )}
            </AnimatePresence>
        </div>
    );
};

export default InsightFeedback;
