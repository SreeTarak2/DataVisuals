import React, { memo, useState } from 'react';
import { Play, Sparkles, MessageSquare, Wrench, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * SqlEditorToolbar — Controls for the SQL Editor
 *
 * Provides buttons for:
 * - Run: Execute the SQL query
 * - Generate: AI generates SQL from natural language description
 * - Explain: AI explains the SQL in plain English
 * - Fix: AI debugs SQL errors
 *
 * Usage:
 *   <SqlEditorToolbar
 *     onRun={() => executeSql()}
 *     onGenerate={(description) => generateSql(description)}
 *     onExplain={() => explainSql()}
 *     onFix={() => fixSql()}
 *     isLoading={false}
 *     hasError={false}
 *     executeLabel="▶ Run"
 *     className="..."
 *   />
 */

const ToolbarButton = memo(({
  icon: Icon,
  label,
  onClick,
  isLoading = false,
  disabled = false,
  variant = 'default',
  shortcut,
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled || isLoading}
      className={cn(
        'sql-editor-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150',
        'focus:outline-none focus:ring-1 focus:ring-accent-primary/40',
        variant === 'primary' && [
          'bg-accent-primary text-white hover:bg-accent-primary-hover',
          'shadow-lg shadow-accent-primary/20',
          'disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none',
        ],
        variant === 'secondary' && [
          'bg-elevated/50 text-secondary hover:text-header hover:bg-elevated',
          'border border-border/50',
          'disabled:opacity-30 disabled:cursor-not-allowed',
        ],
        variant === 'ghost' && [
          'text-muted hover:text-header hover:bg-elevated/50',
          'disabled:opacity-30 disabled:cursor-not-allowed',
        ],
        variant === 'danger' && [
          'bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20',
          'disabled:opacity-30 disabled:cursor-not-allowed',
        ],
      )}
      title={shortcut ? `${label} (${shortcut})` : label}
    >
      {isLoading ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Icon size={14} />
      )}
      <span>{label}</span>
    </button>
  );
});

ToolbarButton.displayName = 'ToolbarButton';

const SqlEditorToolbar = memo(({
  onRun,
  onGenerate,
  onExplain,
  onFix,
  isLoading = false,
  hasError = false,
  className,
}) => {
  const [showGenerateInput, setShowGenerateInput] = useState(false);
  const [generateDescription, setGenerateDescription] = useState('');

  const handleGenerateSubmit = () => {
    if (generateDescription.trim() && onGenerate) {
      onGenerate(generateDescription.trim());
      setGenerateDescription('');
      setShowGenerateInput(false);
    }
  };

  const handleGenerateKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerateSubmit();
    }
    if (e.key === 'Escape') {
      setShowGenerateInput(false);
      setGenerateDescription('');
    }
  };

  return (
    <div className={cn('sql-editor-toolbar', className)}>
      <div className="flex items-center gap-1.5 flex-wrap">
        {/* Run button — primary action */}
        <ToolbarButton
          icon={Play}
          label="Run"
          onClick={onRun}
          isLoading={isLoading}
          disabled={!onRun}
          variant="primary"
          shortcut="⌘⏎"
        />

        <div className="w-px h-4 bg-border mx-1" />

        {/* Generate button — opens inline input */}
        <div className="relative">
          <ToolbarButton
            icon={Sparkles}
            label="Generate"
            onClick={() => setShowGenerateInput(!showGenerateInput)}
            disabled={!onGenerate}
            variant="secondary"
          />

          {/* Inline generate input */}
          {showGenerateInput && (
            <div className="absolute top-full left-0 mt-1.5 z-50 w-80 p-2 rounded-lg bg-surface border border-border shadow-2xl shadow-black/30 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-accent-primary shrink-0" />
                <input
                  autoFocus
                  value={generateDescription}
                  onChange={(e) => setGenerateDescription(e.target.value)}
                  onKeyDown={handleGenerateKeyDown}
                  placeholder="Describe the SQL you need..."
                  className="flex-1 bg-elevated border border-border rounded-md px-2.5 py-1.5 text-xs text-header placeholder:text-muted/50 focus:outline-none focus:border-accent-primary/40"
                />
                <button
                  onClick={handleGenerateSubmit}
                  disabled={!generateDescription.trim()}
                  className="p-1.5 rounded-md bg-accent-primary text-white disabled:opacity-30 hover:bg-accent-primary-hover transition-colors"
                >
                  <Play size={12} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Explain button */}
        <ToolbarButton
          icon={MessageSquare}
          label="Explain"
          onClick={onExplain}
          isLoading={isLoading}
          disabled={!onExplain}
          variant="secondary"
        />

        {/* Fix button — shown when there's an error */}
        {hasError && (
          <ToolbarButton
            icon={Wrench}
            label="Fix with AI"
            onClick={onFix}
            isLoading={isLoading}
            disabled={!onFix}
            variant="danger"
          />
        )}
      </div>
    </div>
  );
});

SqlEditorToolbar.displayName = 'SqlEditorToolbar';

export default SqlEditorToolbar;
