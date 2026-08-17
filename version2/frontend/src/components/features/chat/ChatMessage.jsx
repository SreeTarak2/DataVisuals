/**
 * ChatMessage — Renders a Single Chat Message (User or AI)
 *
 * Extracted from the monolithic SideChatPanel.jsx.
 *
 * User messages: plain bubble with rerun + copy actions.
 * AI messages: markdown content, charts, tables, SQL actions,
 *   transparency indicators, follow-up suggestions, and feedback.
 */
import React, { memo } from 'react';
import {
  BarChart3, RefreshCw, ChevronDown, ChevronUp, ChevronRight,
  Code2, Layers, ArrowRight, Pen,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';

import ChartRenderer from '@/components/features/charts/ChartRenderer';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import CopyButton from '@/components/features/chat/CopyButton';
import QueryResultTable from '@/components/features/chat/QueryResultTable';
import ModernReasoningBlock from '@/components/features/chat/ModernReasoningBlock';
import Logo from '@/components/common/Logo';
import { formatTime, msgVariants } from '@/components/features/chat/chatUtils';

import VersionSwitcher from '@/components/features/chat/VersionSwitcher';

const ChatMessage = memo(({
  msg, isUser, toggleTechnicalDetails, expandedTechnicalDetails,
  onRerun, onSuggestionClick, followUpOverride, msgMeta,
  onEditSql, isDismissed, onInsertSql, onPinToCanvas,
  onEditStart, isEditing, editContent, onEditChange, onEditSubmit, onEditCancel,
  versions = [], currentVersionIndex = 0, onVersionSwitch, onRegenerate,
}) => {
  // ── User message ────────────────────────────────────────────
  if (isUser) {
    return (
      <motion.div className="chat-message--user group" variants={msgVariants} initial="hidden" animate="visible">
        {isEditing ? (
          <div className="chat-edit-container">
            <textarea
              className="chat-edit-textarea"
              value={editContent}
              onChange={(e) => onEditChange(e.target.value)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onEditSubmit(); }
                if (e.key === 'Escape') onEditCancel();
              }}
            />
            <div className="chat-edit-actions">
              <button onClick={onEditCancel} className="chat-action-btn text-[11px]" title="Cancel">Cancel</button>
              <button onClick={onEditSubmit} className="chat-action-btn text-[11px] font-semibold text-ocean" title="Save & Resend">Save & Resend</button>
            </div>
          </div>
        ) : (
          <div className="chat-user-bubble">
            {msg.content}
          </div>
        )}
        <div className="chat-user-footer">
          {msg.timestamp && <span className="chat-timestamp">{formatTime(msg.timestamp)}</span>}
          <div className="chat-user-actions">                            <button onClick={() => onEditStart(msg.id)} className="chat-action-btn" title="Edit">
                              <Pen size={12} />
                            </button>
            <button onClick={() => onRerun(msg.id)} className="chat-action-btn" title="Rerun">
              <RefreshCw size={12} />
            </button>
            <CopyButton text={msg.content} size={12} />
          </div>
        </div>
      </motion.div>
    );
  }

  // ── AI message: follow-ups, content parsing ────────────────
  const canShowFollowUps = msg.show_follow_up_suggestions === true;
  const visibleFollowUps = followUpOverride?.length > 0
    ? followUpOverride
    : canShowFollowUps
      ? (msg.follow_up_suggestions || [])
      : [];

  // Attempt to parse JSON content gracefully if backend returned raw JSON string
  let displayContent = msg.content || '';
  try {
    let cleanStr = displayContent.trim();
    if (cleanStr.startsWith('```json')) cleanStr = cleanStr.substring(7);
    else if (cleanStr.startsWith('```')) cleanStr = cleanStr.substring(3);
    if (cleanStr.endsWith('```')) cleanStr = cleanStr.substring(0, cleanStr.length - 3);
    cleanStr = cleanStr.trim();

    if (cleanStr.startsWith('{') && cleanStr.endsWith('}')) {
      const parsed = JSON.parse(cleanStr);
      if (parsed.response_text) displayContent = parsed.response_text;
      else if (parsed.response) displayContent = parsed.response;
      else if (parsed.message) displayContent = parsed.message;
    }
  } catch (_e) {
    // Not valid JSON, use raw string
  }

  const hasChart = msg.chart_config
    && msg.chart_config.data?.length > 0
    && msg.chart_config.data.some(t => t.x?.length > 0 || t.y?.length > 0);
  const hasTable = msg.result_table && msg.result_table.rows?.length > 0;
  const chartError = msg.chart_config?.data?.[0]?.error;

  return (
    <motion.div
      className={`chat-message--ai ${isDismissed ? 'chat-message--dismissed' : ''}`}
      variants={msgVariants}
      initial="hidden"
      animate="visible"
    >
      <div className="chat-ai-row">
        {/* AI Avatar */}
        <div className="chat-ai-avatar">
          <Logo size={20} />
        </div>

        <div className="chat-ai-body group relative">
          {msg.isCancelled && (
            <div className="flex items-center gap-1.5 text-[10px] text-yellow-700 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 inline-block" />
              Partial response — stopped
            </div>
          )}

          <div className="chat-ai-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre: ({ children }) => {
                  const text = typeof children === 'string'
                    ? children
                    : (children?.props?.children ?? '');
                  return (
                    <div className="chat-code-block">
                      <div className="chat-code-block__header">
                        <span className="chat-code-block__label">Code</span>
                        <CopyButton text={String(text)} size={12} />
                      </div>
                      {children}
                    </div>
                  );
                },
                code: ({ children, ...props }) => <code {...props}>{children}</code>,
                table: (props) => <div className="chat-table-wrapper"><table {...props} /></div>,
              }}
            >
              {displayContent}
            </ReactMarkdown>
          </div>

          {/* Chart */}
          {hasChart && (
            <div className="chat-chart">
              <div className="chat-chart__header">
                <BarChart3 size={13} className="opacity-50" />
                <span className="chat-chart__title">
                  {msg.chart_config.layout?.title?.text || msg.chart_config.layout?.title || 'Visualization'}
                </span>
              </div>
              <div style={{ height: '300px', padding: '4px 0' }}>
                {chartError ? (
                  <div className="chat-chart__empty">
                    <BarChart3 size={32} className="opacity-20" />
                    <span className="chat-chart__empty-text">No data available for this chart</span>
                  </div>
                ) : (
                  <ChartRenderer
                    data={msg.chart_config.data}
                    layout={{
                      ...msg.chart_config.layout,
                      paper_bgcolor: 'transparent',
                      plot_bgcolor: 'transparent',
                      font: { color: 'var(--text-secondary, #6C6E79)', size: 11 },
                      margin: { t: 20, b: 50, l: 50, r: 12 },
                      height: 290,
                      xaxis: { ...(msg.chart_config.layout?.xaxis || {}), gridcolor: 'rgba(255,255,255,0.06)' },
                      yaxis: { ...(msg.chart_config.layout?.yaxis || {}), gridcolor: 'rgba(255,255,255,0.06)' },
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                  />
                )}
              </div>
            </div>
          )}

          <QueryResultTable table={msg.result_table} />

          {/* Transparency indicators */}
          {msgMeta?.sql_fallback && (
            <div className="chat-transparency chat-transparency--warning">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 inline-block shrink-0" />
              Estimate — exact query couldn't execute, response is based on data structure
            </div>
          )}
          {msgMeta?.chart_error && (
            <div className="chat-transparency chat-transparency--error">
              <span className="w-1.5 h-1.5 rounded-full bg-red-600 inline-block shrink-0" />
              Chart couldn't be rendered
            </div>
          )}
          {msgMeta?.column_corrections && Object.keys(msgMeta.column_corrections).length > 0 && (
            <div className="chat-transparency chat-transparency--info">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block shrink-0" />
              Chart column names were adjusted to match your data
            </div>
          )}

          {/* Reasoning Trace */}
          {msg.thinking_steps?.length > 0 && (
            <ModernReasoningBlock thinkingSteps={msg.thinking_steps} isStreaming={false} />
          )}

          {/* Technical Details */}
          {msg.technical_details && (
            <button
              onClick={() => toggleTechnicalDetails(msg.id)}
              className="chat-technical-btn"
              style={{ marginTop: '8px' }}
            >
              {expandedTechnicalDetails[msg.id] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              <span>Logic</span>
            </button>
          )}

          <AnimatePresence>
            {msg.technical_details && expandedTechnicalDetails[msg.id] && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                <div
                  className="chat-technical-content"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(msg.technical_details) }}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Action buttons + timestamp */}
          <div className="chat-ai-footer">
            <div className="chat-ai-actions">
              {msg.sql && (
                <button onClick={() => onEditSql?.(msg.id)} className="chat-action-btn chat-action-btn--sql" title="Edit SQL">
                  <Code2 size={13} />
                </button>
              )}
              {msg.sql && onInsertSql && (
                <button onClick={() => onInsertSql(msg.sql)} className="chat-action-btn" title="Insert in Editor">
                  <ArrowRight size={13} />
                </button>
              )}
              {onPinToCanvas && hasChart && (
                <button onClick={() => onPinToCanvas(msg, 'chart')} className="chat-action-btn" title="Open chart in canvas">
                  <Layers size={13} />
                </button>
              )}
              {onPinToCanvas && hasTable && (
                <button onClick={() => onPinToCanvas(msg, 'table')} className="chat-action-btn" title="Open table in canvas">
                  <Layers size={13} />
                </button>
              )}
              {onPinToCanvas && !hasChart && !hasTable && (
                <button onClick={() => onPinToCanvas(msg, 'text')} className="chat-action-btn" title="Pin as note to canvas">
                  <Layers size={13} />
                </button>
              )}
              <CopyButton text={msg.content} />
              <button onClick={() => onRerun(msg.id)} className="chat-action-btn" title="Regenerate">
                <RefreshCw size={13} />
              </button>
              <InsightFeedback variant="compact" insightText={msg.content?.slice(0, 500) || ''} />
            </div>
            {msg.timestamp && <span className="chat-timestamp">{formatTime(msg.timestamp)}</span>}
          </div>

          {/* Follow-up suggestion chips */}
          {visibleFollowUps.length > 0 && onSuggestionClick && (
            <div className="chat-followups">
              {visibleFollowUps.map((s, i) => (
                <button key={i} onClick={() => onSuggestionClick(s)} className="chat-followup-btn">
                  <ChevronRight size={11} className="shrink-0 opacity-40" />
                  <span>{s}</span>
                </button>
              ))}
            </div>
          )}

          {/* Version Switcher — show when AI message has multiple versions */}
          <VersionSwitcher
            versions={versions}
            currentVersion={currentVersionIndex}
            onSwitch={onVersionSwitch}
            onRegenerate={onRegenerate}
          />
        </div>
      </div>
    </motion.div>
  );
});

ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
