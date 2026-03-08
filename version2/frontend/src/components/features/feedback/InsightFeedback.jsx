/**
 * InsightFeedback Component
 * =========================
 * Professional feedback controls for the Belief Store personalization loop.
 *
 * When a user marks an insight as "useful", "already known", or "incorrect",
 * it trains the Subjective Novelty Filter — storing the insight as an embedding
 * in the per-user ChromaDB Belief Store. Future insights are then scored against
 * existing beliefs via Semantic Surprisal, suppressing redundant findings.
 *
 * Variants:
 *  - compact : Icon-only pill buttons with CSS tooltips (for dense cards)
 *  - inline  : Icons with text labels (for narrative sections)
 */

import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
    ThumbsUp,
    EyeOff,
    Flag,
    Check,
    Loader2,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { agenticAPI } from '@/services/api';

const MotionDiv = motion.div;
const MotionButton = motion.button;

// ── Feedback option definitions ─────────────────────────────────────────────
const FEEDBACK_OPTIONS = [
    {
        type: 'useful',
        icon: ThumbsUp,
        label: 'Useful',
        tooltip: 'This insight is valuable',
        activeColor: 'text-emerald-400',
        hoverText: 'hover:text-emerald-400',
        confirmation: 'Noted as valuable',
    },
    {
        type: 'known',
        icon: EyeOff,
        label: 'Already knew',
        tooltip: 'Already knew this',
        activeColor: 'text-amber-400',
        hoverText: 'hover:text-amber-400',
        confirmation: "Won't repeat similar insights",
    },
    {
        type: 'wrong',
        icon: Flag,
        label: 'Incorrect',
        tooltip: 'This insight seems wrong',
        activeColor: 'text-red-400',
        hoverText: 'hover:text-red-400',
        confirmation: 'Feedback recorded',
    },
];

// ── Spring config for micro-interactions ────────────────────────────────────
const springConfig = { type: 'spring', stiffness: 420, damping: 22 };

// ── Component ───────────────────────────────────────────────────────────────
const InsightFeedback = ({
    insightText,
    datasetId = null,
    variant = 'compact',
    className = '',
}) => {
    const [selected, setSelected] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [confirmed, setConfirmed] = useState(false);

    // ── Submit feedback to the Belief Store API ─────────────────────────────
    const handleFeedback = useCallback(async (feedbackType) => {
        if (selected || isSubmitting) return;

        setSelected(feedbackType);
        setIsSubmitting(true);

        try {
            await agenticAPI.submitFeedback({
                insight_text: insightText,
                feedback_type: feedbackType,
                dataset_id: datasetId,
            });

            setConfirmed(true);

            const option = FEEDBACK_OPTIONS.find((o) => o.type === feedbackType);
            toast.success(option.confirmation, {
                duration: 2500,
                style: {
                    background: '#0f172a',
                    color: '#e2e8f0',
                    // border: '1px solid rgba(255,255,255,0.08)',
                    fontSize: '15px',
                },
                iconTheme: { primary: '#10b981', secondary: '#0f172a' },
            });
        } catch (error) {
            console.error('Feedback submission failed:', error);
            toast.error('Could not save feedback — try again later');
            setSelected(null);
        } finally {
            setIsSubmitting(false);
        }
    }, [insightText, datasetId, selected, isSubmitting]);

    const isCompact = variant === 'compact';

    // ── Confirmed state: settled indicator ──────────────────────────────────
    if (confirmed) {
        const option = FEEDBACK_OPTIONS.find((o) => o.type === selected);
        return (
            <MotionDiv
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={springConfig}
                className={`flex items-center ${className}`}
            >
                <div className={`flex items-center ${isCompact ? 'gap-2' : 'gap-2.5'} ${option.activeColor}`}>
                    <Check className={`${isCompact ? 'w-4 h-4' : 'w-4.5 h-4.5'}`} />
                    <span className={`font-medium ${isCompact ? 'text-xs text-slate-200' : 'text-[11px]'}`}>
                        {isCompact ? 'Saved' : option.confirmation}
                    </span>
                </div>
            </MotionDiv>
        );
    }

    // ── Default state: feedback buttons ──────────────────────────────────────
    return (
        <div
            className={`flex items-center ${isCompact ? 'gap-4.5' : 'gap-4'} ${className}`}
            role="group"
            aria-label="Rate this insight"
        >
            {FEEDBACK_OPTIONS.map((option) => {
                const Icon = option.icon;
                const isSelected = selected === option.type;
                const isOther = selected && !isSelected;

                return (
                    <div key={option.type} className="group/fb relative">
                        {/* Button */}
                        <MotionButton
                            onClick={() => handleFeedback(option.type)}
                            disabled={!!selected || isSubmitting}
                            aria-label={option.tooltip}
                            title={option.label}
                            animate={{
                                opacity: isOther ? 0.25 : 1,
                                scale: isSelected ? 1.12 : 1,
                            }}
                            whileHover={!selected ? { scale: 1.15, y: -1 } : {}}
                            whileTap={!selected ? { scale: 0.92 } : {}}
                            transition={springConfig}
                            className={`
                                relative flex items-center gap-2 rounded-md
                                transition-colors duration-150
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ocean/60
                                ${isCompact ? 'p-0.5' : 'px-1 py-0.5'}
                                ${isSelected
                                    ? `${option.activeColor}`
                                    : `text-slate-400 ${option.hoverText}`
                                }
                                ${isOther ? 'pointer-events-none' : 'cursor-pointer'}
                            `}
                        >
                            {isSelected && isSubmitting ? (
                                <Loader2 className={`w-4.5 h-4.5 animate-spin ${option.activeColor}`} />
                            ) : (
                                <Icon className={`${isCompact ? 'w-4.5 h-4.5' : 'w-5 h-5'}`} />
                            )}
                            {!isCompact && (
                                <span className="text-[11px] font-medium select-none">
                                    {option.label}
                                </span>
                            )}
                        </MotionButton>

                        {/* Tooltip (compact mode only) */}
                        {isCompact && !selected && (
                            <span
                                className="
                                    absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                                    px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap
                                    bg-[#111827] text-slate-100 border border-slate-500/70
                                    opacity-0 group-hover/fb:opacity-100 group-focus-within/fb:opacity-100 pointer-events-none
                                    transition-opacity duration-200 z-[120]
                                    shadow-2xl shadow-black/60
                                    before:absolute before:top-full before:left-1/2 before:-translate-x-1/2
                                    before:border-[5px] before:border-transparent before:border-t-[#111827]
                                "
                                aria-hidden="true"
                            >
                                {option.tooltip}
                            </span>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default InsightFeedback;
