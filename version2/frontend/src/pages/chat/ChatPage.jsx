import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import { Send, Plus, Database, Copy, ChevronDown, ChevronUp, RotateCcw, Pencil, Sparkles, BarChart3, TrendingUp, MessageSquare, Lightbulb, History, Maximize2, X, ArrowRight, Image, Loader2, Brain, Shield, Eye, Square } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import { markdownComponents, streamingMarkdownComponents } from '@/components/features/chat/MarkdownRenderers';
import { ChatErrorDisplay, RateLimitBanner, ThinkingDots, ThinkingSteps } from '@/components/features/chat/ChatErrorDisplay';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useThemeStore from '@/store/themeStore';
import { chatAPI } from '@/services/api';
import useWebSocket from '@/hooks/useWebSocket';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import { AiBotIcon } from '@/components/svg/icons';
import AgenticPanel from '@/components/features/chat/AgenticPanel';
import { PromptInputBox } from '@/components/ui/PromptInputBox';

const getChartTitle = (chartConfig) => (
  chartConfig?.layout?.title?.text || chartConfig?.layout?.title || 'Visualization'
);

const isBackendConversationId = (value) =>
  typeof value === 'string' && /^[a-f0-9]{24}$/i.test(value);

const IconActionButton = ({ icon, label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="group relative inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-secondary transition-colors hover:border-border-strong hover:bg-elevated hover:text-header"
  >
    {React.createElement(icon, { size: 14 })}
    <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-elevated px-2 py-1 text-[10px] font-medium text-header opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
      {label}
    </span>
  </button>
);

const getAxisTitleText = (axisTitle) => {
  if (!axisTitle) return '';
  if (typeof axisTitle === 'string') return axisTitle;
  return axisTitle?.text || '';
};

const getChartMeta = (chartConfig) => {
  const layout = chartConfig?.layout || {};
  const traces = Array.isArray(chartConfig?.data) ? chartConfig.data : [];
  const firstTrace = traces[0] || {};
  const isPieLike = firstTrace?.type === 'pie' || firstTrace?.type === 'donut';

  const existingX = getAxisTitleText(layout?.xaxis?.title);
  const existingY = getAxisTitleText(layout?.yaxis?.title);

  let xLabel = existingX;
  let yLabel = existingY;

  if (!xLabel) {
    if (isPieLike || firstTrace?.labels) xLabel = 'Category';
    else if (firstTrace?.orientation === 'h') xLabel = 'Value';
    else xLabel = 'X Axis';
  }

  if (!yLabel) {
    if (isPieLike || firstTrace?.values) yLabel = 'Value';
    else if (firstTrace?.orientation === 'h') yLabel = 'Category';
    else if (typeof firstTrace?.name === 'string' && !/^trace/i.test(firstTrace.name)) yLabel = firstTrace.name;
    else yLabel = 'Y Axis';
  }

  const pointCount = traces.reduce((count, trace) => {
    if (Array.isArray(trace?.x)) return count + trace.x.length;
    if (Array.isArray(trace?.y)) return count + trace.y.length;
    if (Array.isArray(trace?.values)) return count + trace.values.length;
    return count;
  }, 0);

  return { xLabel, yLabel, pointCount };
};

const buildChartLayout = (chartConfig, height = 380) => {
  const meta = getChartMeta(chartConfig);
  const isDark = document.documentElement.classList.contains('dark');
  const themeColors = isDark ? {
    grid: '#233247',
    zeroline: '#3a4b62',
    tick: '#a8b7cc',
    title: '#c8d3e0',
    font: '#b3c0d4',
    plot_bg: 'rgba(6,8,13,1)'
  } : {
    grid: '#e2e8f0',
    zeroline: '#cbd5e1',
    tick: '#64748b',
    title: '#334155',
    font: '#475569',
    plot_bg: '#f8fafc'
  };

  return {
    ...(chartConfig?.layout || {}),
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: themeColors.plot_bg,
    font: { color: themeColors.font, size: 12, family: 'Rubik, system-ui, sans-serif' },
    height,
    margin: { t: 30, b: 80, l: 60, r: 20 },
    xaxis: {
      ...(chartConfig?.layout?.xaxis || {}),
      title: chartConfig?.layout?.xaxis?.title || { text: meta.xLabel },
      gridcolor: themeColors.grid,
      zerolinecolor: themeColors.zeroline,
      tickfont: { color: themeColors.tick, ...(chartConfig?.layout?.xaxis?.tickfont || {}) },
      titlefont: { color: themeColors.title, ...(chartConfig?.layout?.xaxis?.titlefont || {}) }
    },
    yaxis: {
      ...(chartConfig?.layout?.yaxis || {}),
      title: chartConfig?.layout?.yaxis?.title || { text: meta.yLabel },
      gridcolor: themeColors.grid,
      zerolinecolor: themeColors.zeroline,
      tickfont: { color: themeColors.tick, ...(chartConfig?.layout?.yaxis?.tickfont || {}) },
      titlefont: { color: themeColors.title, ...(chartConfig?.layout?.yaxis?.titlefont || {}) }
    },
  };
};

const withPointMarkers = (chartData = []) => {
  if (!Array.isArray(chartData)) return [];
  return chartData.map((trace) => {
    if (trace?.type !== 'scatter') return trace;
    const currentMode = trace.mode || '';
    if (currentMode.includes('markers')) return trace;
    return {
      ...trace,
      mode: currentMode.includes('lines') ? 'lines+markers' : 'markers',
      marker: {
        size: trace?.marker?.size || 7,
        ...(trace?.marker || {})
      }
    };
  });
};

const extractFollowUpSuggestions = (content = '') => {
  if (!content) return [];

  // ── Pre-processing: normalize inline separator formats ──
  // Some models (Gemini) output: "text --- * Q1? * Q2? * Q3?"
  // Normalize to multi-line: "text\n---\n- Q1?\n- Q2?\n- Q3?"
  let normalized = content.replace(
    /\s*---\s*\*\s*/g,
    (match, offset) => offset === content.indexOf('---') ? '\n---\n- ' : '\n- '
  );
  // Also handle: "--- \n* Q1? * Q2?" or "* Q1? * Q2?" after ---
  if (normalized.includes('---')) {
    const parts = normalized.split(/^---$/m);
    if (parts.length >= 2) {
      const afterSep = parts.slice(1).join('---');
      // Split on " * " patterns (inline bullets)
      const fixed = afterSep.replace(/\s*\*\s+/g, '\n- ');
      normalized = parts[0] + '\n---' + fixed;
    }
  }

  const lines = normalized.split('\n');

  // Try standard anchor first ("you might want to...", "next steps", etc.)
  let anchorIndex = lines.findIndex((line) => /to explore.*further|you might want to|you could also|follow.?up|next.?steps|explore this/i.test(line));

  // Fallback: look for a trailing "---" separator (SQL path uses this)
  if (anchorIndex === -1) {
    for (let i = lines.length - 1; i >= 0; i--) {
      if (/^-{3,}$/.test(lines[i].trim())) {
        anchorIndex = i;
        break;
      }
    }
  }

  if (anchorIndex === -1) return [];

  const suggestions = [];
  for (let i = anchorIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (suggestions.length > 0) break;
      continue;
    }
    // Match bullet points: "- text", "* text", "• text", "1. text"
    const bulletMatch = line.match(/^[-*•\d.]+\s+(.+?)$/);
    if (bulletMatch) {
      const suggestion = bulletMatch[1].replace(/`/g, '').replace(/\*\*/g, '').trim();
      if (suggestion.length > 5) suggestions.push(suggestion);
    } else if (suggestions.length === 0 && line.length > 10 && !line.startsWith('#')) {
      // Non-bullet plain text follow-up (common in SQL path responses)
      const cleaned = line.replace(/`/g, '').replace(/\*\*/g, '').replace(/^["']|["']$/g, '').trim();
      if (cleaned.length > 10 && /\?|explore|try|look|compare|check|break|analyze/i.test(cleaned)) {
        suggestions.push(cleaned);
      }
    } else if (suggestions.length > 0 && !bulletMatch) {
      break;
    }
    if (suggestions.length >= 4) break;
  }

  return suggestions;
};

const stripFollowUpSection = (content = '') => {
  if (!content) return '';

  // ── Normalize inline separator formats (same as extractFollowUpSuggestions) ──
  // Handles: "text --- * Q1? * Q2?" → multi-line
  let normalized = content;
  if (/---\s*\*/.test(normalized)) {
    normalized = normalized.replace(
      /\s*---\s*\*\s*/g,
      (match, offset) => offset === normalized.indexOf('---') ? '\n---\n- ' : '\n- '
    );
  }
  if (normalized.includes('---')) {
    const parts = normalized.split(/^---$/m);
    if (parts.length >= 2) {
      const afterSep = parts.slice(1).join('---');
      const fixed = afterSep.replace(/\s*\*\s+/g, '\n- ');
      normalized = parts[0] + '\n---' + fixed;
    }
  }

  const lines = normalized.split('\n');

  // First, try anchor-phrase detection
  let anchorIndex = lines.findIndex((line) => /to explore.*further|you might want to|you could also|follow.?up|next.?steps|explore this/i.test(line));

  // Fallback: detect bare --- separator (used by SQL path responses)
  if (anchorIndex === -1) {
    anchorIndex = lines.findIndex((line) => /^---\s*$/.test(line.trim()));
  }

  if (anchorIndex === -1) return content;

  let endIndex = anchorIndex + 1;
  for (let i = anchorIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (i > anchorIndex + 1) {
        endIndex = i + 1;
        break;
      }
      continue;
    }
    const isBullet = /^[-*•]\s+(.+?)$/.test(line);
    if (isBullet) {
      endIndex = i + 1;
      continue;
    }
    // For --- separator, also consume non-bullet follow-up lines (plain text questions)
    if (/\?|explore|try|look|compare|check|break|analyze/i.test(line)) {
      endIndex = i + 1;
      continue;
    }
    if (i > anchorIndex + 1) {
      break;
    }
  }

  // If --- was the separator, strip it too
  const cleanedLines = [...lines.slice(0, anchorIndex), ...lines.slice(endIndex)];
  return cleanedLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
};

const LEGACY_SQL_DETAILS_REGEX = /<details>\s*<summary>[\s\S]*?View SQL Query[\s\S]*?<\/summary>\s*```sql\s*([\s\S]*?)```\s*<\/details>/i;

const extractLegacySqlBlock = (content = '') => {
  if (!content) return { content: '', sql: null };
  const match = content.match(LEGACY_SQL_DETAILS_REGEX);
  if (!match) return { content, sql: null };

  const cleanedContent = content
    .replace(LEGACY_SQL_DETAILS_REGEX, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return {
    content: cleanedContent,
    sql: (match[1] || '').trim() || null,
  };
};

// Memoized message component to prevent re-renders when typing
const ChatMessage = memo(({ msg, index, isUser, timestamp, editingMessageId, editContent, setEditContent, handleEditKeyDown, cancelEdit, saveEdit, startEditMessage, handleRerunMessage, copyToClipboard, toggleTechnicalDetails, expandedTechnicalDetails, highlightImportantText, onExpandChart, onCopyChart, onSuggestionClick, followUpOverride, onOpenAgenticPanel, isLastAiMessage }) => {
  if (isUser) {
    const isEditing = editingMessageId === msg.id;

    return (
      <motion.div
        key={msg.id || index}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2 }}
        className="flex flex-col items-end px-4 py-3 group"
      >
        {/* User Message Bubble — minimal dark pill, right-aligned */}
        <div
          className={cn(
            "relative border border-border",
            isEditing
              ? "w-full max-w-[860px] rounded-2xl"
              : "max-w-[78%] md:max-w-[76%] rounded-2xl rounded-br-sm px-4 py-3"
          )}
          style={{
            backgroundColor: isEditing ? 'var(--bg-elevated)' : 'var(--bg-surface)',
            border: '1px solid var(--border)',
            wordBreak: 'break-word',
            overflowWrap: 'anywhere',
          }}
        >
          {isEditing ? (
            <div className="rounded-xl bg-surface p-2 shadow-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleEditKeyDown}
                className="w-full min-h-[112px] resize-none rounded-xl bg-primary px-4 py-3 text-[16px] leading-relaxed text-header shadow-inner outline-none transition-all placeholder:text-muted focus:border-accent-primary focus:ring-2 focus:ring-accent-primary/50"
                style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-header)', borderColor: 'var(--border)' }}
                // autoFocus
                rows={3}
              />
              <div className="mt-3 flex flex-col gap-3 px-1 sm:flex-row sm:items-center sm:justify-end">
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={cancelEdit}
                    className="rounded-xl border border-border px-5 py-2 text-sm text-secondary transition-colors hover:border-border-strong hover:bg-elevated hover:text-header"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveEdit}
                    className="rounded-xl bg-zinc-300 px-5 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-200"
                  >
                    Save
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-[16px] leading-[1.62] whitespace-pre-wrap text-pearl-soft">
              {msg.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {msg.content.replace(/^\[Context:[^\]]*\]\s*/i, '')}
                </ReactMarkdown>
              ) : (
                <span className="text-red-400 text-sm italic">[Message content missing]</span>
              )}
            </div>
          )}
        </div>

        {/* Footer row: timestamp + action icons */}
        {!isEditing && (
          <div className="flex items-center gap-2 mt-1.5 pr-1">
            {timestamp && (
              <span className="text-text-text-xs text-muted tabular-nums opacity-0 group-hover:opacity-100 transition-opacity duration-200">{timestamp}</span>
            )}
            {msg.isEdited && (
              <span className="text-[10px] text-muted italic">(edited)</span>
            )}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              {!editingMessageId && (
                <>
                  <button
                    onClick={() => handleRerunMessage(msg.id)}
                    className="p-1 text-muted hover:text-secondary rounded-md transition-colors"
                    title="Rerun this query"
                  >
                    <RotateCcw size={15} />
                  </button>
                  <button
                    onClick={() => startEditMessage(msg)}
                    className="p-1 text-muted hover:text-secondary rounded-md transition-colors"
                    title="Edit message"
                  >
                    <Pencil size={15} />
                  </button>
                </>
              )}
              <button
                onClick={() => copyToClipboard(msg.content)}
                className="p-1 text-muted hover:text-secondary rounded-md transition-colors"
                title="Copy to clipboard"
              >
                <Copy size={15} />
              </button>
            </div>
          </div>
        )}
      </motion.div>
    );
  }

  // AI Message — keep existing design
  const { content: contentWithoutLegacySql, sql: legacySql } = extractLegacySqlBlock(msg.content || '');
  const sqlText = (msg.sql || legacySql || '').trim();
  // Prefer structured follow-ups from backend; fall back to text parsing
  const followUpSuggestions = followUpOverride?.length > 0
    ? followUpOverride
    : extractFollowUpSuggestions(contentWithoutLegacySql);
  const cleanedContent = (followUpOverride?.length > 0
    ? contentWithoutLegacySql
    : stripFollowUpSection(contentWithoutLegacySql)
  ).replace(/^>\s*\*\*TL;DR:\*\*[^\n]*\n*/i, '').trimStart();

  return (
    <motion.div
      key={msg.id || index}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="relative px-4 py-4 group"
    >
      {/* AI Avatar */}
      <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center rounded-full shadow-lg bg-surface border border-border text-header overflow-hidden">
        <AiBotIcon className="w-5 h-5" />
      </div>

      {/* AI Message Container */}
      <div
        className={cn(
          "mx-auto flex w-full flex-col items-start pl-12",
          msg.chart_config ? "max-w-[48rem]" : "max-w-[42rem]"
        )}
      >
        {/* Name and Timestamp */}
        {/* <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-medium text-secondary">DataSage AI</span>
          {timestamp && (
            <span className="text-[10px] text-muted">{timestamp}</span>
          )}
        </div> */}

        {/* Cancelled / partial response badge */}
        {msg.isCancelled && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px] text-amber-400/80">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400/70" />
            Response stopped — partial answer shown
          </div>
        )}

        {/* AI Message Content */}
        <div className="text-pearl-soft px-1 break-words overflow-hidden text-[15px] leading-[1.72]" style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
          {cleanedContent ? (
            <div className="max-w-none [&>*:last-child]:mb-0 overflow-hidden">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {cleanedContent}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-red-400 text-sm italic">[Message content missing]</div>
          )}
        </div>

        {sqlText && (
          <details className="group mt-1 mb-2 w-full overflow-hidden rounded-xl border border-border bg-surface shadow-lg">
            <summary className="flex list-none w-full cursor-pointer items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-elevated/30 [&::-webkit-details-marker]:hidden">
              <div className="flex items-center gap-2">
                <Database size={14} className="text-secondary" />
                <span className="text-xs font-medium tracking-wide text-secondary">SQL QUERY</span>
              </div>
              <ChevronDown size={14} className="text-secondary group-open:hidden" />
              <ChevronUp size={14} className="hidden text-secondary group-open:block" />
            </summary>
            <div className="overflow-hidden border-t border-border px-3 py-2 bg-surface">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {['```sql', sqlText, '```'].join('\n')}
              </ReactMarkdown>
            </div>
          </details>
        )}

        {/* Chart Block — Centered between text and suggestions */}
        {msg.chart_config && (
            <div className="my-5 w-full overflow-hidden rounded-2xl bg-surface shadow-lg border border-border">
            <div className="bg-elevated/30 px-4 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BarChart3 size={15} className="text-secondary shrink-0" />
                    <span className="text-[15px] font-semibold tracking-tight text-header break-words">
                      {getChartTitle(msg.chart_config)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <IconActionButton icon={Copy} label="Copy Chart" onClick={() => onCopyChart(msg.chart_config)} />
                  <IconActionButton icon={Maximize2} label="Expand Chart" onClick={() => onExpandChart(msg.chart_config)} />
                </div>
              </div>
            </div>
            {msg.chart_config?.data && msg.chart_config.data.length > 0 ? (
              <div className="p-2 pt-0">
                <PlotlyChart
                  data={withPointMarkers(msg.chart_config.data)}
                  layout={buildChartLayout(msg.chart_config, 460)}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted text-sm">
                Chart data unavailable
              </div>
            )}
          </div>
        )}

        {/* Technical Details Expandable */}
        {msg.technical_details && (
          <div className="mt-2 w-full">
            <button
              onClick={() => toggleTechnicalDetails(msg.id || index)}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-secondary transition-colors"
            >
              {expandedTechnicalDetails[msg.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>Technical Details</span>
            </button>
            <AnimatePresence>
              {expandedTechnicalDetails[msg.id || index] && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div
                    className="mt-2 p-3 bg-surface rounded-lg text-xs text-secondary border border-border"
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(highlightImportantText(msg.technical_details)) }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* AI Action Buttons */}
        <div className="flex items-center gap-4 mt-2 opacity-80 group-hover:opacity-100 transition-opacity duration-200">
          <button
            onClick={() => copyToClipboard(msg.content)}
            className="p-0.5 text-muted hover:text-accent-primary rounded-md transition-colors"
            title="Copy to clipboard"
          >
            <Copy size={18} />
          </button>
          {msg.content && <InsightFeedback variant="compact" insightText={msg.content.slice(0, 500)} />}
        </div>

        {/* Follow-up Suggestions — prominent clickable cards at the bottom */}
        {followUpSuggestions.length > 0 && (
          <div className="mt-4 w-full">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Explore further</p>
            <div className="flex flex-col gap-2">
              {followUpSuggestions.map((suggestion, suggestionIndex) => (
                <button
                  key={`${msg.id || index}-suggestion-${suggestionIndex}`}
                  type="button"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="group/sugg flex items-center gap-3 w-full text-left rounded-xl border border-border bg-surface px-4 py-3 text-[14px] text-pearl-soft transition-all duration-200 hover:bg-elevated hover:border-border-strong hover:shadow-lg"
                >
                  <Lightbulb size={15} className="text-muted shrink-0 group-hover/sugg:text-accent-warning transition-colors" />
                  <span className="flex-1 leading-snug">{suggestion}</span>
                  <ArrowRight size={14} className="text-muted-foreground shrink-0 group-hover/sugg:text-secondary group-hover/sugg:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Deep Analysis nudge — only on the latest AI response */}
        {isLastAiMessage && onOpenAgenticPanel && (
          <div className="mt-4 w-full">
            <button
              type="button"
              onClick={onOpenAgenticPanel}
              className="group/snd flex items-center gap-2.5 w-full text-left rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-2.5 text-[13px] text-violet-300/80 transition-all duration-200 hover:bg-violet-500/10 hover:border-violet-500/35 hover:text-violet-200"
            >
              <Brain size={14} className="shrink-0 text-violet-400/70 group-hover/snd:text-violet-300 transition-colors" />
              <span className="flex-1">Run deep statistical analysis on this dataset</span>
              <ArrowRight size={13} className="text-violet-400/50 group-hover/snd:translate-x-0.5 transition-transform" />
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
});

ChatMessage.displayName = 'ChatMessage';

const Chat = () => {
  const {
    getCurrentConversationMessages,
    sendMessage,
    loading,
    setCurrentConversation,
    getConversation,
    loadConversations,
    startNewConversation,
    // Streaming state
    isStreaming,
    streamingContent,
    startStreaming,
    appendStreamingToken,
    finishStreaming,
    cancelStreaming,
    currentConversationId,
    setLoading,
    editMessage,
    rerunMessage
  } = useChatStore();
  const { selectedDataset, setSelectedDataset, datasets } = useDatasetStore();
  const [inputMessage, setInputMessage] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  // Handle prefilled query from insights "Investigate" button
  useEffect(() => {
    if (location.state?.prefillQuery) {
      setInputMessage(location.state.prefillQuery);
      // Clear the state so it doesn't persist on refresh
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state?.prefillQuery]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const composerRef = useRef(null);
  // pendingConvIdRef: the local convId used when a message was sent so onDone can
  // migrate messages from the temp ID to the backend-assigned ID when they differ.
  const pendingConvIdRef = useRef(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showAgenticPanel, setShowAgenticPanel] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});
  const [streamingChartConfig, setStreamingChartConfig] = useState(null);
  const streamingChartConfigRef = useRef(null); // Ref to track latest chart for race condition fix
  const currentClientMessageIdRef = useRef(null); // Ref to track in-flight WS message for cancel
  const [expandedChartConfig, setExpandedChartConfig] = useState(null);
  const [composerHeight, setComposerHeight] = useState(180);

  // Image attachment state
  const [pendingImages, setPendingImages] = useState([]);  // { id, file, previewUrl, uploading, url }
  const fileInputRef = useRef(null);

  // Edit state
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editContent, setEditContent] = useState('');

  // Error and rate limit state
  const [chatError, setChatError] = useState(null);
  const [rateLimitRemaining, setRateLimitRemaining] = useState(null);
  const [rateLimitCountdown, setRateLimitCountdown] = useState(null); // seconds until reset
  // Structured follow-up suggestions from the latest AI response (indexed by message id)
  const [followUpMap, setFollowUpMap] = useState({}); // { [msgId]: string[] }
  const lastStreamingMsgIdRef = useRef(null);
  const [showRateLimitBanner, setShowRateLimitBanner] = useState(true);

  // Thinking-steps state (Copilot-style pipeline transparency)
  const [thinkingSteps, setThinkingSteps] = useState([]);

  // Rerun state machine for professional rerun experience
  // States: 'idle' | 'clearing' | 'loading' | 'streaming' | 'complete'
  const [rerunState, setRerunState] = useState('idle');

  // Privacy state
  // const [privacySettings, setPrivacySettings] = useState(null);

  const messages = getCurrentConversationMessages();
  const isAITyping = loading || isStreaming;

  // Track message count to prevent unnecessary scrolls
  const messageCountRef = useRef(0);
  const pendingMessageRef = useRef(null);

  // Rate limit total (matches backend MAX_WS_MESSAGES_PER_MINUTE)
  const RATE_LIMIT_TOTAL = 30;

  // WebSocket connection for streaming
  const { isConnected, connect, sendMessage: wsSendMessage, sendCancel } = useWebSocket({
    onToken: useCallback((token) => {
      appendStreamingToken(token);
      scrollToBottom();
    }, [appendStreamingToken]),

    onResponseComplete: useCallback((fullResponse) => {
      // Use fullResponse as fallback if tokens didn't accumulate properly
      if (fullResponse) {
        const currentContent = useChatStore.getState().streamingContent;
        if (!currentContent || currentContent.trim().length < fullResponse.trim().length * 0.5) {
          // streamingContent is empty or significantly shorter — replace with full response
          useChatStore.setState({ streamingContent: fullResponse });
        }
      }
    }, []),

    onChart: useCallback((chartConfig) => {
      // Update both state and ref to ensure we have the latest chart
      setStreamingChartConfig(chartConfig);
      streamingChartConfigRef.current = chartConfig;
    }, []),

    onThinkingStep: useCallback((label) => {
      // Transition from loading to streaming when first thinking step arrives
      if (rerunState === 'loading') {
        setRerunState('streaming');
      }
      setThinkingSteps(prev => [...prev, label]);
    }, [rerunState]),

    onDone: useCallback(({ conversationId, chartConfig, sql, follow_up_suggestions, rate_limit_remaining }) => {
      const localConvId = pendingConvIdRef.current;

      // Reset rerun state to idle
      setRerunState('idle');

      // Update rate limit counter from done message
      if (rate_limit_remaining !== null && rate_limit_remaining !== undefined) {
        setRateLimitRemaining(rate_limit_remaining);
      }

      // Store structured follow-up suggestions keyed by the streaming message id
      if (follow_up_suggestions?.length > 0 && lastStreamingMsgIdRef.current) {
        setFollowUpMap(prev => ({ ...prev, [lastStreamingMsgIdRef.current]: follow_up_suggestions }));
      }

      if (conversationId && localConvId && conversationId !== localConvId) {
        // Backend assigned a different ID (first message of a new conversation).
        // Migrate the user message(s) from the temp local conv into the backend conv
        // so user and AI messages always live in the same conversation.
        useChatStore.setState(state => {
          const tempConv = state.conversations[localConvId];
          if (!tempConv) return { currentConversationId: conversationId };
          const newConversations = { ...state.conversations };
          delete newConversations[localConvId];
          newConversations[conversationId] = { ...tempConv, id: conversationId };
          return { conversations: newConversations, currentConversationId: conversationId };
        });
        setCurrentChatId(conversationId);
        setCurrentConversation(conversationId);
      } else if (conversationId) {
        // Existing conversation — just sync both state pointers.
        setCurrentChatId(conversationId);
        setCurrentConversation(conversationId);
      }

      // Finalize the streamed message (store already has the correct currentConversationId)
      const content = useChatStore.getState().streamingContent;
      // Use chartConfig from backend, or fall back to the most recent streamed chart (via ref)
      const finalChartConfig = chartConfig || streamingChartConfigRef.current || streamingChartConfig;
      finishStreaming(content, finalChartConfig, sql);
      setStreamingChartConfig(null);
      streamingChartConfigRef.current = null;
      currentClientMessageIdRef.current = null;
      setThinkingSteps([]);

      // Update URL params
      const finalConvId = conversationId || localConvId;
      if (finalConvId) {
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', finalConvId);
        const dsId = selectedDataset?.id || selectedDataset?._id;
        if (dsId) newParams.set('dataset', dsId);
        setSearchParams(newParams, { replace: true });
      }
    }, [finishStreaming, streamingChartConfig, searchParams, selectedDataset, setSearchParams, setCurrentConversation]),

    onError: useCallback((error) => {
      cancelStreaming();
      setThinkingSteps([]);
      setRerunState('idle');
      setChatError(error);
      const detail = String(error?.detail || '').toLowerCase();
      if (detail.includes('rate') || detail.includes('limit')) {
        // Start a 60s countdown so user knows when they can send again
        const retryAfter = error?.retry_after_seconds || 60;
        setRateLimitCountdown(retryAfter);
        const interval = setInterval(() => {
          setRateLimitCountdown(prev => {
            if (prev <= 1) { clearInterval(interval); return null; }
            return prev - 1;
          });
        }, 1000);
      } else {
        toast.error(error?.detail || 'Connection error');
      }
    }, [cancelStreaming]),

    onStatus: useCallback((status) => {
      // Track rate limit remaining from status updates
      if (status?.rate_limit_remaining !== undefined) {
        setRateLimitRemaining(status.rate_limit_remaining);
      }
      // Clear any previous errors when processing starts
      setChatError(null);
    }, []),

    autoConnect: false
  });

  // Connect WebSocket when dataset is selected
  useEffect(() => {
    if (selectedDataset?.id && !isConnected) {
      connect();
    }
  }, [selectedDataset?.id, isConnected, connect]);

  // Fetch privacy settings when dataset is selected
  // useEffect(() => {
  //   const fetchPrivacySettings = async () => {
  //     const datasetId = selectedDataset?.id || selectedDataset?._id;
  //     if (!datasetId) return;

  //     try {
  //       const res = await privacyAPI.getDatasetSettings(datasetId);
  //       setPrivacySettings(res.data);
  //     } catch (err) {
  //       console.error('Failed to fetch privacy settings:', err);
  //       setPrivacySettings(null);
  //     }
  //   };

  //   fetchPrivacySettings();
  // }, [selectedDataset]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (!composerRef.current) return;

    const updateComposerHeight = () => {
      const measuredHeight = composerRef.current?.offsetHeight || 180;
      setComposerHeight(measuredHeight);
    };

    updateComposerHeight();
    const resizeObserver = new ResizeObserver(updateComposerHeight);
    resizeObserver.observe(composerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  // Detect code blocks like ChatGPT
  const containsCodeBlock = (text) => {
    if (!text) return false;
    return text.includes("```") || /<pre.*?>|<code.*?>/i.test(text);
  };

  // Only scroll when message count changes (NOT when typing or AI typing state changes)
  useEffect(() => {
    const currentCount = messages.length;
    if (currentCount !== messageCountRef.current) {
      scrollToBottom();
      messageCountRef.current = currentCount;
    }
  }, [messages.length]);

  useEffect(() => {
    const initializeChat = async () => {
      await loadConversations();
      const chatId = searchParams.get('chatId');
      if (chatId) {
        setCurrentChatId(chatId);
        const conversation = getConversation(chatId);
        if (conversation) {
          setCurrentConversation(chatId);
        } else {
          toast.error('Conversation not found');
        }
      } else {
        setCurrentChatId(null);
        setCurrentConversation(null);
      }

      const datasetId = searchParams.get('dataset');
      if (datasetId && datasets.length > 0) {
        const dataset = datasets.find(d => d.id === datasetId);
        if (dataset) {
          setSelectedDataset(dataset);
        }
      }
    };
    initializeChat();
  }, [searchParams, getConversation, setCurrentConversation, loadConversations, datasets, setSelectedDataset]);

  const handleSendMessage = async (e, messageText = null) => {
    e?.preventDefault();
    let message = messageText || inputMessage.trim();
    // Issue 5: normalise id shape — backend may return either .id or ._id
    const datasetId = selectedDataset?.id || selectedDataset?._id;

    // Check if any images are still uploading
    const stillUploading = pendingImages.some(img => img.uploading);
    if (stillUploading) {
      toast.error('Please wait for images to finish uploading');
      return;
    }

    // Prepend uploaded image markdown to the message
    const uploadedImages = pendingImages.filter(img => img.url);
    if (uploadedImages.length > 0) {
      const imageMarkdown = uploadedImages.map(img => `![](${img.url})`).join('\n');
      message = message ? `${imageMarkdown}\n${message}` : imageMarkdown;
    }

    if (!message || isAITyping || !datasetId) return;

    if (!messageText) {
      setInputMessage('');
    }

    // Clear pending images and revoke blob URLs
    if (uploadedImages.length > 0) {
      pendingImages.forEach(img => {
        if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
      });
      setPendingImages([]);
    }

    // Store message for retry on failure
    pendingMessageRef.current = message;
    let convId = currentChatId || currentConversationId;
    if (!convId) {
      convId = startNewConversation(datasetId);
      setCurrentChatId(convId);
    }

    // Issue 1: record convId so onDone can migrate the conversation if the backend
    // returns a different ID (which happens on the very first message).
    pendingConvIdRef.current = convId;

    // Add user message immediately to UI exactly once (for both WS and HTTP paths)
    const userMessage = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    useChatStore.setState(state => ({
      conversations: {
        ...state.conversations,
        [convId]: {
          ...state.conversations[convId],
          messages: [
            ...(state.conversations[convId]?.messages || []),
            userMessage
          ]
        }
      }
    }));

    // Try WebSocket streaming first
    if (isConnected) {
      const msgId = `msg_${Date.now()}_ai`;
      lastStreamingMsgIdRef.current = msgId;
      startStreaming(msgId);

      const clientMsgId = wsSendMessage({
        message,
        datasetId,
        // Issue 1: use convId not stale currentChatId (React state update is async)
        conversationId: isBackendConversationId(convId) ? convId : null,
        streaming: true
      });
      currentClientMessageIdRef.current = clientMsgId;
    } else {
      // Issue 2: user message is already appended above; tell the store action to
      // skip adding it again to prevent the duplicate-message bug.
      const result = await sendMessage(message, datasetId, convId, { skipUserMessage: true });
      if (result && !result.success) {
        toast.error(result.error);
      }
      if (result && result.conversationId) {
        setCurrentChatId(result.conversationId);
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', result.conversationId);
        if (datasetId) newParams.set('dataset', datasetId);
        setSearchParams(newParams, { replace: true });
      }
    }
  };

  // Re-execute a query without adding a new user message (for edit/rerun)
  const reExecuteQuery = async (message, convId) => {
    const datasetId = selectedDataset?.id || selectedDataset?._id;
    if (!message || isAITyping || !datasetId) return;

    // Try WebSocket streaming first
    if (isConnected) {
      console.log('Re-executing via WebSocket (streaming)');
      const msgId = `msg_${Date.now()}_ai`;
      startStreaming(msgId);

      const clientMsgId = wsSendMessage({
        message,
        datasetId,
        conversationId: isBackendConversationId(convId) ? convId : null,
        streaming: true
      });
      currentClientMessageIdRef.current = clientMsgId;
    } else {
      // Issue 2: the caller (editMessage / rerunMessage) already manages the user
      // message in the store — skip adding it again here.
      const result = await sendMessage(message, datasetId, convId, { skipUserMessage: true });
      if (result && !result.success) {
        toast.error(result.error);
      }
    }
  };

  const handleRerunMessage = (messageId) => {
    // Complete state reset to fix emoji glitch and ensure clean rerun
    const resetForRerun = () => {
      // Cancel any ongoing streaming
      if (isStreaming) {
        cancelStreaming();
      }
      // Clear thinking steps
      setThinkingSteps([]);
      // Clear streaming content
      useChatStore.setState({ streamingContent: '' });
      setStreamingChartConfig(null);
      streamingChartConfigRef.current = null;
      // Reset rerun state machine
      setRerunState('clearing');
      // After brief clearing animation, move to loading
      setTimeout(() => setRerunState('loading'), 200);
    };

    resetForRerun();

    const result = rerunMessage(messageId, currentChatId);

    if (result?.success) {
      // rerunMessage already truncated the AI response and kept the user
      // message in place — use reExecuteQuery so we don't append another copy
      reExecuteQuery(result.content, result.conversationId || currentChatId);
    } else {
      toast.error('Failed to rerun message');
      setRerunState('idle');
    }
  };

  const handleSuggestionClick = (suggestion) => {
    handleSendMessage(null, suggestion);
  };

  const handleStopGeneration = useCallback(() => {
    const clientMsgId = currentClientMessageIdRef.current;
    if (clientMsgId) {
      sendCancel(clientMsgId);
    }
    cancelStreaming();
    setThinkingSteps([]);
    setRerunState('idle');
    currentClientMessageIdRef.current = null;
  }, [sendCancel, cancelStreaming]);

  // Edit message handlers
  const startEditMessage = (msg) => {
    setEditingMessageId(msg.id);
    setEditContent(msg.content);
  };

  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditContent('');
  };

  const saveEdit = async () => {
    if (!editContent.trim() || !editingMessageId) {
      cancelEdit();
      return;
    }

    const result = editMessage(editingMessageId, editContent.trim(), currentChatId);

    if (result?.success) {
      if (result.truncatedCount > 0) {
        toast.success(`Edited message. ${result.truncatedCount} message(s) removed.`);
      }

      // Clear edit state
      cancelEdit();

      // Re-execute the edited message without adding new user message
      reExecuteQuery(result.newContent, result.conversationId);
    } else {
      toast.error('Failed to edit message');
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      saveEdit();
    } else if (e.key === 'Escape') {
      cancelEdit();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
      if (textareaRef.current) {
        textareaRef.current.style.height = '68px';
        textareaRef.current.classList.remove('scrolled');
      }
    }
  };

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const minHeight = 68;
    const maxHeight = 380;

    // Store current scroll position of the chat container to prevent jumping
    const chatContainer = textarea.closest('.overflow-y-auto')?.parentElement?.querySelector('.overflow-y-auto');
    const scrollTop = chatContainer?.scrollTop;

    // Temporarily set to auto to measure, but do it without triggering reflow on the chat
    const currentHeight = textarea.style.height;
    textarea.style.height = 'auto';
    const newHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight));
    textarea.style.height = `${newHeight}px`;

    // Restore scroll position if it changed
    if (chatContainer && scrollTop !== undefined) {
      chatContainer.scrollTop = scrollTop;
    }

    if (newHeight >= maxHeight) {
      textarea.classList.add('scrolled');
    } else {
      textarea.classList.remove('scrolled');
    }
  }, []);

  // ── Image upload helpers ──────────────────────────────────────────────
  const uploadImage = useCallback(async (file) => {
    const id = `img_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const previewUrl = URL.createObjectURL(file);

    // Validate on client side
    if (!file.type.startsWith('image/')) {
      toast.error('Only image files are allowed');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be under 5 MB');
      return;
    }

    // Add with loading state
    setPendingImages(prev => [...prev, { id, file, previewUrl, uploading: true, url: null }]);

    try {
      const res = await chatAPI.uploadChatImage(file);
      const url = res.data.url;
      setPendingImages(prev =>
        prev.map(img => img.id === id ? { ...img, uploading: false, url } : img)
      );
    } catch (err) {
      toast.error('Image upload failed');
      setPendingImages(prev => prev.filter(img => img.id !== id));
      URL.revokeObjectURL(previewUrl);
    }
  }, []);

  const removePendingImage = useCallback((id) => {
    setPendingImages(prev => {
      const img = prev.find(i => i.id === id);
      if (img?.previewUrl) URL.revokeObjectURL(img.previewUrl);
      return prev.filter(i => i.id !== id);
    });
  }, []);

  const handlePaste = useCallback(async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageItem = Array.from(items).find(
      (item) => item.kind === 'file' && item.type.startsWith('image/')
    );
    if (!imageItem) {
      // Normal text paste — just adjust height
      setTimeout(adjustTextareaHeight, 0);
      return;
    }

    e.preventDefault();
    const file = imageItem.getAsFile();
    if (file) uploadImage(file);
  }, [uploadImage, adjustTextareaHeight]);

  const handleFileSelect = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    files.forEach(f => uploadImage(f));
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [uploadImage]);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch (err) {
      toast.error('Failed to copy');
    }
  };

  const toggleTechnicalDetails = (messageId) => {
    setExpandedTechnicalDetails(prev => ({ ...prev, [messageId]: !prev[messageId] }));
  };

  const openExpandedChart = (chartConfig) => {
    setExpandedChartConfig(chartConfig);
  };

  const closeExpandedChart = () => {
    setExpandedChartConfig(null);
  };

  const copyChartAsImage = async (chartConfig) => {
    let Plotly = null;
    let container = null;
    try {
      if (!chartConfig?.data?.length) {
        toast.error('Chart data unavailable');
        return;
      }

      Plotly = (await import('plotly.js-dist-min')).default;
      container = document.createElement('div');
      container.style.position = 'fixed';
      container.style.left = '-10000px';
      container.style.top = '-10000px';
      container.style.width = '1600px';
      container.style.height = '900px';
      document.body.appendChild(container);

      await Plotly.newPlot(
        container,
        chartConfig.data,
        buildChartLayout(chartConfig, 900),
        { staticPlot: true, displayModeBar: false, responsive: false }
      );

      const imageData = await Plotly.toImage(container, {
        format: 'png',
        width: 1600,
        height: 900,
        scale: 2
      });

      const response = await fetch(imageData);
      const blob = await response.blob();

      if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([new window.ClipboardItem({ [blob.type]: blob })]);
        toast.success('Chart copied as image');
      } else {
        const link = document.createElement('a');
        link.href = imageData;
        link.download = 'chart.png';
        link.click();
        toast.success('Clipboard image is not supported here. Downloaded PNG instead.');
      }
    } catch (err) {
      console.error('Failed to copy chart image', err);
      toast.error('Failed to copy chart image');
    } finally {
      if (container) {
        try {
          if (Plotly) {
            Plotly.purge(container);
          }
        } catch (cleanupError) {
          console.error('Failed to cleanup temporary chart container', cleanupError);
        }
        try {
          if (typeof container.remove === 'function') {
            container.remove();
          } else if (container.parentNode?.contains(container)) {
            container.parentNode.removeChild(container);
          }
        } catch (detachError) {
          console.error('Failed to detach temporary chart container', detachError);
        }
      }
    }
  };

  useEffect(() => {
    if (!expandedChartConfig) return;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeExpandedChart();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [expandedChartConfig]);

  const highlightImportantText = useCallback((text) => {
    if (!text) return '';
    const cleanText = text.replace(/<[^>]*>/g, '');
    const isDark = document.documentElement.classList.contains('dark');
    const blueColor = isDark ? 'text-blue-400' : 'text-blue-600';
    const greenColor = isDark ? 'text-green-400' : 'text-green-600';
    const blueSoftColor = isDark ? 'text-blue-300' : 'text-blue-500';

    return cleanText
      .replace(/(\d+\.?\d*%)/g, `<span class="${blueColor} font-semibold">$1</span>`)
      .replace(/(\$\d+[,.]?\d*)/g, `<span class="${greenColor} font-semibold">$1</span>`)
      .replace(/\b(correlation|trend|pattern|insight|significant|increase|decrease)\b/gi, `<span class="${blueSoftColor} font-medium">$1</span>`)
      .replace(/(["'])([^"']+)\1/g, `<span class="${blueSoftColor} font-mono text-xs">$1$2$1</span>`)
      .replace(/\n/g, '<br>');
  }, []);

  // Generate starter suggestions based on selected dataset
  const starterSuggestions = useMemo(() => {
    if (!selectedDataset) return [];
    const name = selectedDataset.name || 'your dataset';
    return [
      { icon: TrendingUp, text: `What are the key trends in this data?`, color: 'from-blue-500/20 to-blue-600/20 border-blue-500/30' },
      { icon: BarChart3, text: `Show me a summary of the most important metrics`, color: 'from-blue-500/15 to-blue-700/20 border-blue-500/25' },
      { icon: Lightbulb, text: `What unusual patterns or outliers exist?`, color: 'from-blue-400/15 to-blue-600/20 border-blue-400/25' },
      { icon: MessageSquare, text: `Give me an executive summary of this dataset`, color: 'from-blue-300/10 to-blue-500/20 border-blue-300/25' },
    ];
  }, [selectedDataset]);

  if (!selectedDataset) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-6">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <Database className="w-16 h-16 text-primary mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-foreground mb-2">Select a Dataset</h2>
          <p className="text-muted-foreground">Choose a dataset to start chatting with the AI.</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background relative">
      <div className="absolute top-3 right-4 z-20 flex items-center gap-2">
        <button
          onClick={() => {
            const newId = startNewConversation(selectedDataset.id);
            setCurrentChatId(newId);
            const newParams = new URLSearchParams();
            if (selectedDataset?.id) newParams.set('dataset', selectedDataset.id);
            setSearchParams(newParams, { replace: true });
          }}
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border text-secondary hover:text-header hover:bg-elevated transition-colors shadow-inner cursor-pointer"
          title="New Chat"
          aria-label="Start a new chat"
        >
          <Plus size={15} />
          <span className="hidden sm:inline text-sm">New Chat</span>
        </button>
        <button
          onClick={() => setShowHistoryModal(true)}
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border text-secondary hover:text-header hover:bg-elevated transition-colors shadow-inner cursor-pointer"
          title="Chat History"
          aria-label="Open chat history"
        >
          <History size={15} />
          <span className="hidden sm:inline text-sm">History</span>
        </button>
        <button
          onClick={() => setShowAgenticPanel(p => !p)}
          className={`inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-colors shadow-inner cursor-pointer ${showAgenticPanel
            ? 'border-violet-500/60 text-violet-400 bg-violet-500/10'
            : 'border-border text-secondary hover:text-header hover:bg-elevated'
            }`}
          title="Subjective Novelty Detection — run analysis & view Belief Graph"
          aria-label="Toggle SND panel"
        >
          <Brain size={15} />
          <span className="hidden sm:inline text-sm">SND</span>
        </button>
        {/* Privacy Badge */}
        {/* <button
          onClick={() => window.location.href = '/app/settings'}
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          title="Privacy settings - click to configure"
          aria-label="Privacy settings"
        >
          <Shield size={15} />
          <span className="hidden sm:inline text-sm">Privacy</span>
        </button> */}
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-hidden relative">
        <div
          className="mx-auto max-w-[52rem] pt-3"
          style={{ paddingBottom: `${composerHeight + 28}px` }}
        >
          {/* Rate Limit Warning Banner */}
          {rateLimitRemaining !== null && showRateLimitBanner && (
            <RateLimitBanner
              remaining={rateLimitRemaining}
              total={RATE_LIMIT_TOTAL}
              onClose={() => setShowRateLimitBanner(false)}
            />
          )}

          {/* Error Display */}
          <AnimatePresence>
            {chatError && (
              <ChatErrorDisplay
                error={chatError}
                onRetry={() => {
                  const lastMessage = pendingMessageRef.current;
                  setChatError(null);
                  if (lastMessage) {
                    handleSendMessage(null, lastMessage);
                  }
                }}
                onDismiss={() => setChatError(null)}
              />
            )}
          </AnimatePresence>

          {/* Starter Suggestions — shown when no messages */}
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center justify-center pt-16 pb-8 px-4"
            >
              <h2 className="text-4xl font-bold text-header mb-4 mt-12 tracking-tight">What can I help you explore?</h2>
              <p className="text-lg text-secondary leading-relaxed mb-10 text-center max-w-2xl">
                Ask anything about <span className="text-accent-primary font-semibold">{selectedDataset?.name || 'your dataset'}</span>.<br className="hidden sm:block" />
                I can analyze trends, generate charts, find patterns, and provide deep data insights.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
                {starterSuggestions.map((suggestion, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    onClick={(e) => handleSendMessage(e, suggestion.text)}
                    className={cn(
                      "group flex items-center gap-4 px-5 py-4 rounded-2xl border border-border text-left transition-all duration-300 cursor-pointer",
                      "bg-surface/80 hover:bg-elevated hover:border-accent-primary/20 hover:scale-[1.01] hover:shadow-xl shadow-sm"
                    )}
                  >
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-accent-primary/10 group-hover:bg-accent-primary/20 transition-colors">
                      <suggestion.icon size={20} className="text-accent-primary" />
                    </div>
                    <span className="text-[15px] font-medium text-header group-hover:text-accent-primary transition-colors leading-snug">
                      {suggestion.text}
                    </span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence mode="popLayout" initial={false}>
            {messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              const timestamp = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
              // Show deep analysis nudge on last AI message only (not while AI is typing)
              const isLastAiMessage = !isUser && !isAITyping && index === messages.length - 1;

              return (
                <ChatMessage
                  key={msg.id || index}
                  msg={msg}
                  index={index}
                  isUser={isUser}
                  timestamp={timestamp}
                  editingMessageId={editingMessageId}
                  editContent={editContent}
                  setEditContent={setEditContent}
                  handleEditKeyDown={handleEditKeyDown}
                  cancelEdit={cancelEdit}
                  saveEdit={saveEdit}
                  startEditMessage={startEditMessage}
                  handleRerunMessage={handleRerunMessage}
                  copyToClipboard={copyToClipboard}
                  toggleTechnicalDetails={toggleTechnicalDetails}
                  expandedTechnicalDetails={expandedTechnicalDetails}
                  highlightImportantText={highlightImportantText}
                  onExpandChart={openExpandedChart}
                  onCopyChart={copyChartAsImage}
                  onSuggestionClick={handleSuggestionClick}
                  followUpOverride={followUpMap[msg.id] || null}
                  isLastAiMessage={isLastAiMessage}
                  onOpenAgenticPanel={() => setShowAgenticPanel(true)}
                />
              );
            })}
          </AnimatePresence>

          {/* Streaming indicator with avatar */}
          {isAITyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="relative px-4 py-4"
            >
              {/* AI Avatar */}
              <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-surface border border-border shadow-lg text-header overflow-hidden">
                <AiBotIcon className="w-5 h-5 animate-pulse" />
              </div>

              {/* Message Container */}
              <div className="mx-auto flex w-full max-w-[42rem] flex-col items-start pl-12">
                <div className="px-1 text-pearl-soft">
                  {isStreaming && streamingContent ? (
                    <div className="max-w-none">
                      {thinkingSteps.length > 0 && (
                        <ThinkingSteps
                          steps={thinkingSteps}
                          isStreaming={true}
                          className="mb-3"
                        />
                      )}
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={streamingMarkdownComponents}
                      >
                        {streamingContent}
                      </ReactMarkdown>
                      <span className="thinking-cursor" />
                    </div>
                  ) : rerunState === 'loading' || rerunState === 'clearing' ? (
                    <ThinkingDots stage="reanalyzing" />
                  ) : thinkingSteps.length > 0 ? (
                    <ThinkingSteps steps={thinkingSteps} isStreaming={false} />
                  ) : (
                    <ThinkingDots stage={loading ? 'analyzing' : 'generating'} />
                  )}
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area with glassmorphism effect like Grok */}
      <div
        ref={composerRef}
        className="absolute bottom-0 left-0 right-0 px-4 py-3 pointer-events-none"
        style={{
          background: 'linear-gradient(to top, var(--bg-primary) 0%, var(--bg-primary)/0.6 52%, transparent 100%)',
        }}
      >
        <div className="mx-auto max-w-[55rem] pointer-events-auto">
          {/* Hidden file input for attachment button in PromptInputBox */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Rate-limit usage bar — shown when we have remaining count or a countdown */}
          {(rateLimitRemaining !== null || rateLimitCountdown !== null) && (
            <div className="mb-2 px-1">
              {rateLimitCountdown !== null ? (
                <div className="flex items-center gap-2 text-[11px] text-amber-400">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  Rate limit reached — resets in <strong>{rateLimitCountdown}s</strong>
                </div>
              ) : rateLimitRemaining !== null && rateLimitRemaining <= 10 ? (
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-border overflow-hidden">
                    <div
                      className={cn(
                        "h-1 rounded-full transition-all",
                        rateLimitRemaining <= 3 ? "bg-red-500" : "bg-amber-400"
                      )}
                      style={{ width: `${(rateLimitRemaining / RATE_LIMIT_TOTAL) * 100}%` }}
                    />
                  </div>
                  <span className={cn(
                    "text-[10px] tabular-nums",
                    rateLimitRemaining <= 3 ? "text-red-400" : "text-amber-400/80"
                  )}>
                    {rateLimitRemaining}/{RATE_LIMIT_TOTAL} left
                  </span>
                </div>
              ) : null}
            </div>
          )}

          <PromptInputBox
            value={inputMessage}
            onChange={setInputMessage}
            onSend={(msg) => handleSendMessage(null, msg)}
            onStop={handleStopGeneration}
            isLoading={isAITyping}
            pendingImages={pendingImages}
            onRemoveImage={removePendingImage}
            onAttachClick={() => fileInputRef.current?.click()}
          />
        </div>
      </div>

      <AnimatePresence>
        {showAgenticPanel && (
          <AgenticPanel
            datasetId={selectedDataset?.id || selectedDataset?._id}
            onClose={() => setShowAgenticPanel(false)}
          />
        )}
      </AnimatePresence>

      <ChatHistoryModal
        isOpen={showHistoryModal}
        onClose={() => setShowHistoryModal(false)}
        currentConversationId={currentChatId}
        onSelectConversation={(id) => {
          const conv = getConversation(id);
          setCurrentConversation(id);
          setCurrentChatId(id);
          setShowHistoryModal(false);

          // Issue 3: sync selectedDataset to the dataset the conversation was created with
          // so subsequent queries are grounded in the correct data, not whatever is
          // currently selected globally.
          if (conv?.datasetId) {
            const matchingDataset = datasets.find(
              d => (d.id || d._id) === conv.datasetId
            );
            if (matchingDataset) setSelectedDataset(matchingDataset);
          }

          const newParams = new URLSearchParams(searchParams);
          newParams.set('chatId', id);
          const urlDatasetId = conv?.datasetId || selectedDataset?.id || selectedDataset?._id;
          if (urlDatasetId) newParams.set('dataset', urlDatasetId);
          setSearchParams(newParams, { replace: true });
        }}
      />

      <AnimatePresence>
        {expandedChartConfig && (
          <motion.div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeExpandedChart}
          >
            <motion.div
              layoutId={expandedChartConfig?.id}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.16 }}
              className="w-full max-w-6xl overflow-hidden rounded-2xl bg-surface shadow-2xl border border-border"
              onClick={(event) => event.stopPropagation()}
            >
              {/* Header */}
              <div className="bg-elevated/35 px-3 py-2 backdrop-blur-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-accent-primary/10">
                        <BarChart3 size={14} className="text-accent-primary shrink-0" />
                      </div>
                      <span className="text-sm font-semibold text-header truncate">
                        {getChartTitle(expandedChartConfig)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <IconActionButton icon={Copy} label="Copy Chart" onClick={() => copyChartAsImage(expandedChartConfig)} />
                    <IconActionButton icon={X} label="Close" onClick={closeExpandedChart} />
                  </div>
                </div>
              </div>
              <div className="p-2 pt-0">
                <PlotlyChart
                  data={withPointMarkers(expandedChartConfig.data)}
                  layout={buildChartLayout(expandedChartConfig, 700)}
                  config={{ displayModeBar: true, responsive: true }}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div >
  );
};

export default Chat;
