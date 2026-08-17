/**
 * ModernReasoningBlock — Collapsible AI Reasoning Trace
 *
 * Shows the AI's chain-of-thought with per-step labels, detail,
 * source tags, evidence snippets, and confidence indicators.
 *
 * Mirrors the ChatGPT o1 / Claude 3.5 Sonnet style.
 */
import React, { useState, useEffect, memo } from 'react';
import { Loader2, Sparkles, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const defaultSteps = [
  'Analyzing query intent & dataset schema',
  'Formulating SQL transformations & aggregations',
  'Synthesizing charts and data insights',
];

const ModernReasoningBlock = memo(({ thinkingSteps = [], isStreaming = true }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Live timer for elapsed reasoning time
  useEffect(() => {
    if (!isStreaming) return;
    const startTime = Date.now();
    const interval = setInterval(() => {
      setElapsedTime(((Date.now() - startTime) / 1000).toFixed(1));
    }, 100);
    return () => clearInterval(interval);
  }, [isStreaming]);

  const steps = thinkingSteps.length > 0 ? thinkingSteps : defaultSteps;

  return (
    <div className="mb-2 text-xs font-sans">
      {/* Minimal Unbordered Text Trigger (Clean ChatGPT / Claude Style) */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-1.5 py-0.5 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer group select-none"
      >
        {isStreaming ? (
          <Loader2 size={13} className="animate-spin text-zinc-400 group-hover:text-zinc-200 transition-colors" />
        ) : (
          <Sparkles size={13} className="text-zinc-400 group-hover:text-zinc-200 transition-colors" />
        )}
        <span className="text-[12px] font-medium tracking-tight">
          {isStreaming ? `Thinking (${elapsedTime}s)...` : `Thought for ${elapsedTime || steps.length}s`}
        </span>
        <ChevronDown
          size={12}
          className={`text-zinc-500 group-hover:text-zinc-300 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Expanded Reasoning Log */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-l border-zinc-800 ml-1.5 pl-3.5 my-2 space-y-2 font-sans">
              {steps.map((step, idx) => {
                const isCurrent = isStreaming && idx === steps.length - 1;
                const isDone = !isStreaming || idx < steps.length - 1;
                const labelText = typeof step === 'string' ? step : step?.label || 'Processing step';
                const detailText = typeof step === 'object' ? step?.detail : null;
                const sourceText = typeof step === 'object' ? step?.source : null;
                const evidenceText = typeof step === 'object' ? step?.evidence : null;
                const confidenceVal = typeof step === 'object' ? step?.confidence : null;
                return (
                  <div key={idx}>
                    <div className="flex items-center gap-2 text-zinc-400">
                      {isCurrent ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-200 shrink-0" />
                      ) : isDone ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-500/70 shrink-0" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-700/50 shrink-0" />
                      )}
                      <span className={`text-[11.5px] ${isCurrent ? 'text-zinc-200 font-medium' : 'text-zinc-400'}`}>
                        {labelText}
                      </span>
                      {sourceText && (
                        <span className="text-[9.5px] uppercase tracking-wider text-zinc-600 font-medium">
                          {sourceText}
                        </span>
                      )}
                      {confidenceVal && (
                        <span className={`text-[9.5px] font-medium ${
                          confidenceVal === 'computed_from_data'
                            ? 'text-emerald-500'
                            : confidenceVal === 'estimate'
                              ? 'text-amber-500'
                              : 'text-zinc-500'
                        }`}>
                          ●
                        </span>
                      )}
                    </div>
                    {detailText && (
                      <p className="text-[11px] text-zinc-500 ml-[18px] mt-0.5 leading-snug">
                        {detailText}
                      </p>
                    )}
                    {evidenceText && (
                      <p
                        className="text-[10px] text-zinc-600 ml-[18px] mt-0.5 font-mono leading-snug truncate max-w-full"
                        title={evidenceText}
                      >
                        ⟐ {evidenceText}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

ModernReasoningBlock.displayName = 'ModernReasoningBlock';

export default ModernReasoningBlock;
