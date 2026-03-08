/**
 * Recommendations — Priority-numbered cards with category borders and AI CTA
 */
import React from 'react';
import { motion } from 'framer-motion';
import { Lightbulb, Shield, Copy, AlertTriangle, GitBranch, AlertCircle, BarChart, TrendingUp, Layers, CheckCircle, ArrowRight, MessageSquare } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

const ICONS = { 'shield': Shield, 'copy': Copy, 'alert-triangle': AlertTriangle, 'git-branch': GitBranch, 'alert-circle': AlertCircle, 'bar-chart': BarChart, 'trending-up': TrendingUp, 'layers': Layers, 'check-circle': CheckCircle, 'lightbulb': Lightbulb };

const CAT = {
    critical:     { border: 'border-l-red-500',    numBg: 'bg-red-500/15 text-red-400 border-red-500/30',     iconBg: 'bg-red-500/10 border-red-500/20',     iconColor: 'text-red-400',     badge: 'bg-red-500/15 text-red-400 border-red-500/25',     badgeText: 'Urgent'        },
    data_quality: { border: 'border-l-amber-500',  numBg: 'bg-amber-500/15 text-amber-400 border-amber-500/30', iconBg: 'bg-amber-500/10 border-amber-500/20', iconColor: 'text-amber-400',   badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20', badgeText: 'Data Quality'  },
    relationship: { border: 'border-l-blue-500',   numBg: 'bg-blue-500/15 text-blue-400 border-blue-500/30',   iconBg: 'bg-blue-500/10 border-blue-500/20',   iconColor: 'text-blue-400',    badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20',   badgeText: 'Relationship'  },
    anomaly:      { border: 'border-l-red-500',    numBg: 'bg-red-500/10 text-red-400 border-red-500/20',      iconBg: 'bg-red-500/10 border-red-500/20',     iconColor: 'text-red-400',     badge: 'bg-red-500/10 text-red-400 border-red-500/20',      badgeText: 'Anomaly'       },
    distribution: { border: 'border-l-purple-500', numBg: 'bg-purple-500/15 text-purple-400 border-purple-500/30', iconBg: 'bg-purple-500/10 border-purple-500/20', iconColor: 'text-purple-400', badge: 'bg-purple-500/10 text-purple-400 border-purple-500/20', badgeText: 'Distribution' },
    trend:        { border: 'border-l-emerald-500',numBg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', iconBg: 'bg-emerald-500/10 border-emerald-500/20', iconColor: 'text-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', badgeText: 'Trend' },
    segment:      { border: 'border-l-purple-500', numBg: 'bg-purple-500/15 text-purple-400 border-purple-500/30', iconBg: 'bg-purple-500/10 border-purple-500/20', iconColor: 'text-purple-400', badge: 'bg-purple-500/10 text-purple-400 border-purple-500/20', badgeText: 'Segment' },
    positive:     { border: 'border-l-emerald-600',numBg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', iconBg: 'bg-emerald-500/10 border-emerald-500/20', iconColor: 'text-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', badgeText: 'Positive' },
};

const PROMPTS = {
    investigate: r => `Help me investigate: "${r.title}". ${r.description}. Where should I start?`,
    explore:     r => `Help me explore: "${r.title}". ${r.description}. Show me what to look for.`,
    transform:   r => `Help me fix: "${r.title}". ${r.description}. Give me step-by-step guidance.`,
    monitor:     r => `Help me set up monitoring for: "${r.title}". ${r.description}. What metrics should I track?`,
    segment:     r => `Help me analyze: "${r.title}". ${r.description}. What deeper patterns can we find?`,
    critical:    r => `This is urgent: "${r.title}". ${r.description}. What should I do immediately?`,
};

const RecCard = ({ rec, index, onInvestigate }) => {
    const cfg  = CAT[rec.category] || CAT.data_quality;
    const Icon = ICONS[rec.icon] || Lightbulb;
    const getPrompt = PROMPTS[rec.action_type] || (r => r.description);

    return (
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.05 }}
            className={cn('flex items-start gap-4 p-4 rounded-xl border-l-4 border bg-[var(--surface-1)] hover:bg-[var(--surface-2)] transition-all duration-200', 'border-[var(--surface-border)]', cfg.border)}
        >
            <div className="flex flex-col items-center gap-1 shrink-0">
                <div className={cn('w-8 h-8 rounded-lg border flex items-center justify-center font-bold text-xs tabular-nums', cfg.numBg)}>
                    {String((rec.priority !== undefined ? rec.priority : index) + 1).padStart(2, '0')}
                </div>
                {rec.urgency_score !== undefined && (
                    <div className="w-8 text-center">
                        <div className="h-1 w-full rounded-full overflow-hidden" style={{ backgroundColor: 'var(--surface-2)' }}>
                            <div
                                className={cn('h-full rounded-full transition-all',
                                    rec.urgency_score >= 80 ? 'bg-red-400' :
                                    rec.urgency_score >= 50 ? 'bg-amber-400' : 'bg-emerald-400'
                                )}
                                style={{ width: `${Math.min(rec.urgency_score, 100)}%` }}
                            />
                        </div>
                        <span className="text-[9px] font-mono" style={{ color: 'var(--page-muted)' }}>{Math.round(rec.urgency_score)}</span>
                    </div>
                )}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-start gap-2 mb-1.5 flex-wrap">
                    <div className={cn('w-6 h-6 rounded-md border flex items-center justify-center shrink-0', cfg.iconBg)}>
                        <Icon className={cn('w-3.5 h-3.5', cfg.iconColor)} />
                    </div>
                    <span className="text-[13px] font-semibold flex-1 leading-snug" style={{ color: 'var(--page-text)' }}>{rec.title}</span>
                    <span className={cn('text-xs px-1.5 py-0.5 rounded-full border font-semibold shrink-0', cfg.badge)}>{cfg.badgeText}</span>
                </div>
                <p className="text-xs leading-relaxed mb-3" style={{ color: 'var(--page-text)' }}>{renderBold(rec.description)}</p>
                <div className="flex items-center gap-3">
                    <button onClick={() => onInvestigate(getPrompt(rec))}
                        className="flex items-center gap-1.5 text-[13px] transition-colors font-medium"
                        style={{ color: 'var(--accent-primary)' }}
                    >
                        <MessageSquare className="w-3 h-3" />
                        Get AI guidance <ArrowRight className="w-2.5 h-2.5" />
                    </button>
                    <InsightFeedback insightId={rec.id} />
                </div>
            </div>
        </motion.div>
    );
};

const Recommendations = ({ recommendations = [], compact = false, onViewAll, onInvestigate }) => {
    if (recommendations.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Actions Required</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>Your data looks great! No major issues detected.</p>
            </div>
        );
    }

    const criticalRecs = recommendations.filter(r => r.category === 'critical').length;

    return (
        <div className="backdrop-blur-sm rounded-2xl overflow-hidden border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
            <div className="px-5 pt-5 pb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-violet-500/10 border border-violet-500/20 rounded-xl flex items-center justify-center">
                        <Lightbulb className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Action Plan</h3>
                        <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                            {recommendations.length} prioritized action{recommendations.length !== 1 ? 's' : ''}
                            {criticalRecs > 0 && <span className="text-red-400 ml-1">· {criticalRecs} urgent</span>}
                        </p>
                    </div>
                </div>
                {compact && onViewAll && (
                    <button onClick={onViewAll} className="flex items-center gap-1 text-xs transition-colors" style={{ color: 'var(--page-muted)' }}>
                        View all <ArrowRight className="w-3 h-3" />
                    </button>
                )}
            </div>
            <div className="px-5 pb-5 space-y-2.5">
                {recommendations.map((rec, i) => (
                    <RecCard key={rec.id || i} rec={rec} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default Recommendations;
