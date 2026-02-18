import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    BrainCircuit,
    Search,
    BarChart2,
    CheckCircle2,
    Sparkles,
    AlertCircle,
    TrendingUp,
    ArrowRight,
    BookOpen
} from 'lucide-react';
import GlassPanel from '@/components/ui/GlassPanel';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import ReactMarkdown from 'react-markdown';

// --- Thinking Animation Component ---
const ThinkingState = ({ onComplete }) => {
    const steps = [
        { id: 'planner', label: 'PLANNER: Scanning dataset schema & generating hypotheses...', icon: BrainCircuit, color: 'text-purple-400' },
        { id: 'analyst', label: 'ANALYST: Running statistical regression & correlation checks...', icon: Search, color: 'text-blue-400' },
        { id: 'critic', label: 'CRITIC: Validating P-values & Effect Sizes...', icon: AlertCircle, color: 'text-amber-400' },
        { id: 'novelty', label: 'NOVELTY FILTER: Checking Long-Term Memory for known facts...', icon: Sparkles, color: 'text-pink-400' },
        { id: 'synthesizer', label: 'SYNTHESIZER: Compiling narrative & visualizations...', icon: BookOpen, color: 'text-emerald-400' }
    ];

    const [currentStep, setCurrentStep] = useState(0);

    useEffect(() => {
        if (currentStep < steps.length) {
            const timer = setTimeout(() => {
                setCurrentStep(prev => prev + 1);
            }, 1500 + Math.random() * 1000); // Random duration between 1.5s - 2.5s per step
            return () => clearTimeout(timer);
        } else {
            setTimeout(onComplete, 800); // Short pause before finishing
        }
    }, [currentStep, steps.length, onComplete]);

    return (
        <div className="flex flex-col items-center justify-center h-full p-8">
            <div className="w-full max-w-md space-y-6">
                <h3 className="text-xl font-bold text-center text-pearl mb-8 tracking-widest">
                    AI AGENT WATCHTOWER
                </h3>

                <div className="space-y-4">
                    {steps.map((step, idx) => {
                        const isActive = idx === currentStep;
                        const isCompleted = idx < currentStep;
                        const Icon = step.icon;

                        return (
                            <motion.div
                                key={step.id}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{
                                    opacity: isActive || isCompleted ? 1 : 0.3,
                                    x: 0,
                                    scale: isActive ? 1.02 : 1
                                }}
                                className={`flex items-center gap-4 p-4 rounded-lg border transition-all ${isActive
                                        ? 'bg-white/5 border-ocean/50 shadow-[0_0_15px_rgba(0,240,255,0.1)]'
                                        : isCompleted
                                            ? 'bg-transparent border-transparent'
                                            : 'bg-transparent border-transparent'
                                    }`}
                            >
                                <div className={`p-2 rounded-full ${isActive ? 'bg-ocean/20 animate-pulse' : isCompleted ? 'bg-emerald-500/10' : 'bg-white/5'
                                    }`}>
                                    {isCompleted ? (
                                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                    ) : (
                                        <Icon className={`w-5 h-5 ${isActive ? step.color : 'text-gray-500'}`} />
                                    )}
                                </div>
                                <span className={`text-sm font-mono ${isActive ? 'text-pearl font-bold' : isCompleted ? 'text-gray-400' : 'text-gray-600'}`}>
                                    {step.label}
                                </span>
                                {isActive && (
                                    <span className="ml-auto w-2 h-2 rounded-full bg-ocean animate-ping" />
                                )}
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

// --- Narrative Story Component ---
const DeepAnalysisStory = ({ analysisResult, isLoading }) => {
    const [showThinking, setShowThinking] = useState(true);

    // If loading is true, ensure we show thinking state
    useEffect(() => {
        if (isLoading) {
            setShowThinking(true);
        }
    }, [isLoading]);

    // If we have a result and thinking is done (or if we shouldn't show thinking anymore)
    // But strictly, we want to show thinking AT LEAST until processing is done.
    // We'll manage state: Thinking -> Result.

    const handleThinkingComplete = () => {
        // Only switch to result if data is actually ready. 
        // If backend is still loading, we might show a "Finalizing..." spinner or keep the last step active.
        // Ideally, the parent component controls 'isLoading'. 
        if (!isLoading) {
            setShowThinking(false);
        }
    };

    // If backend finishes FAST, we still want to show the animation sequence? 
    // User asked for animation that "complements" real working.
    // We can force the animation to play through.

    // Revised Logic:
    // 1. showThinking starts TRUE.
    // 2. ThinkingState plays its sequence.
    // 3. onComplete checks if isLoading is false. If yes, setShowThinking(false). 
    // 4. If isLoading is still true, we wait.

    // BUT: ThinkingState has fixed timers. 

    return (
        <div className="w-full h-full relative overflow-y-auto scrollbar-thin scrollbar-thumb-ocean/20 scrollbar-track-transparent bg-black/40">
            <AnimatePresence mode="wait">
                {(showThinking || isLoading) ? (
                    <motion.div
                        key="thinking"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="absolute inset-0 z-50 bg-noir/90 backdrop-blur-md"
                    >
                        <ThinkingState onComplete={() => setShowThinking(false)} />
                    </motion.div>
                ) : (
                    <motion.div
                        key="story"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8 }}
                        className="p-6 md:p-10 max-w-4xl mx-auto space-y-12"
                    >
                        {/* Header Section */}
                        <div className="border-b border-white/10 pb-8">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="px-2 py-1 bg-ocean/10 border border-ocean/30 rounded text-[10px] text-ocean tracking-widest font-bold uppercase">
                                    DEEP ANALYSIS REPORT
                                </span>
                                <span className="text-muted-foreground text-xs font-mono">
                                    {new Date().toLocaleDateString()}
                                </span>
                            </div>
                            <h1 className="text-3xl md:text-5xl font-bold text-pearl font-display leading-tight">
                                Data Narrative
                            </h1>
                        </div>

                        {/* Introduction / Context */}
                        <div className="prose prose-invert prose-lg max-w-none">
                            <ReactMarkdown>
                                {analysisResult?.response || "Analysis complete."}
                            </ReactMarkdown>
                        </div>

                        {/* Interactive Charts Section */}
                        {analysisResult?.charts?.length > 0 && (
                            <div className="space-y-12">
                                <h2 className="text-2xl font-bold text-pearl border-l-4 border-ocean pl-4">
                                    Visual Evidence
                                </h2>
                                <div className="grid grid-cols-1 gap-8">
                                    {analysisResult.charts.map((chart, idx) => (
                                        <GlassPanel key={idx} className="p-1 border border-white/5 bg-black/20 overflow-hidden">
                                            <div className="p-4 border-b border-white/5 flex justify-between items-center bg-white/5">
                                                <h3 className="font-bold text-sm tracking-wide text-gray-200">
                                                    FIG {idx + 1}. {chart.insight_type?.toUpperCase()}
                                                </h3>
                                                <div className="flex gap-2">
                                                    {/* Actions like expand could go here */}
                                                </div>
                                            </div>
                                            <div className="h-[400px] w-full p-4">
                                                <PlotlyChart
                                                    data={chart.data}
                                                    layout={{
                                                        ...chart.layout,
                                                        paper_bgcolor: 'rgba(0,0,0,0)',
                                                        plot_bgcolor: 'rgba(0,0,0,0)',
                                                        font: { color: '#e2e8f0' },
                                                        autosize: true
                                                    }}
                                                    config={{ responsive: true, displayModeBar: false }}
                                                    style={{ width: '100%', height: '100%' }}
                                                />
                                            </div>
                                            <div className="p-4 text-sm text-gray-400 italic bg-black/20">
                                                {chart.description}
                                            </div>
                                        </GlassPanel>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Summary / Stats Footprint */}
                        {analysisResult?.stats && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-8 border-t border-white/10 opacity-60">
                                <div>
                                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Insights Found</div>
                                    <div className="text-xl font-mono text-ocean">{analysisResult.insights?.length || 0}</div>
                                </div>
                                <div>
                                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Novelty Score</div>
                                    <div className="text-xl font-mono text-purple-400">
                                        {analysisResult.insights?.[0]?.novelty_score?.toFixed(2) || 'N/A'}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Boring Filtered</div>
                                    <div className="text-xl font-mono text-gray-400">{analysisResult.boring_filtered || 0}</div>
                                </div>
                            </div>
                        )}

                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default DeepAnalysisStory;
