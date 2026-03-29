import React, { useState } from 'react';
import { X, Check, ChevronRight } from 'lucide-react';

/**
 * ClarificationCard - Shows what DataSage understood before answering
 * 
 * Props:
 *   - originalQuery: The raw user query
 *   - whatIUnderstood: Plain English explanation of what will be shown
 *   - needsClarification: Boolean indicating if user should confirm
 *   - onConfirm: Function to call when user confirms
 *   - onCancel: Function to call when user cancels
 *   - onEdit: Function to call when user wants to edit
 */
const ClarificationCard = ({
  originalQuery,
  whatIUnderstood,
  needsClarification = true,
  onConfirm,
  onCancel,
  onEdit,
  loading = false,
}) => {
  const [showOptions, setShowOptions] = useState(false);

  if (!whatIUnderstood) return null;

  return (
    <div className="clarification-card" style={{
      background: 'linear-gradient(135deg, var(--accent-primary-light) 0%, var(--accent-primary-light) 100%)',
      border: '1px solid var(--accent-primary)',
      borderOpacity: 0.3,
      borderRadius: '12px',
      padding: '16px',
      marginBottom: '16px',
      animation: 'slideIn 0.3s ease-out',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginBottom: '12px',
      }}>
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-primary-hover) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '14px',
          fontWeight: '600',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
        </div>
        <div>
          <div style={{
            fontSize: '13px',
            fontWeight: '600',
            color: 'var(--accent-primary)',
          }}>
            Here's what I understood
          </div>
          <div style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
          }}>
            {needsClarification ? 'Confirm before I answer' : 'Just a moment...'}
          </div>
        </div>
      </div>

      <div style={{
        background: 'var(--bg-elevated)',
        borderRadius: '12px',
        padding: '10px 12px',
        marginBottom: '12px',
        border: '1px solid var(--border)',
      }}>
        <div style={{
          fontSize: '11px',
          color: 'var(--text-muted)',
          marginBottom: '4px',
        }}>
          You asked:
        </div>
        <div style={{
          fontSize: '13px',
          color: 'var(--text-header)',
          fontStyle: 'italic',
        }}>
          "{originalQuery}"
        </div>
      </div>

      {/* What DataSage will show */}
      <div style={{
        padding: '12px',
        background: 'var(--accent-primary-light)',
        borderRadius: '8px',
        borderLeft: '3px solid var(--accent-primary)',
        marginBottom: '16px',
      }}>
        <div style={{
          fontSize: '11px',
          color: 'var(--accent-primary)',
          marginBottom: '6px',
          fontWeight: '500',
        }}>
          I'm going to:
        </div>
        <div style={{
          fontSize: '14px',
          color: 'var(--text-primary)',
          lineHeight: '1.5',
        }}>
          {whatIUnderstood}
        </div>
      </div>

      {/* Actions */}
      {needsClarification && !loading && (
        <div style={{
          display: 'flex',
          gap: '8px',
        }}>
          <button
            onClick={onConfirm}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '10px 16px',
              background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-primary-hover) 100%)',
              border: 'none',
              borderRadius: '8px',
              color: 'white',
              fontSize: '13px',
              fontWeight: '500',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = 'translateY(-1px)';
              e.target.style.boxShadow = '0 4px 12px rgba(99, 102, 241, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'translateY(0)';
              e.target.style.boxShadow = 'none';
            }}
          >
            <Check size={14} />
            That's right
          </button>

          <button
            onClick={() => setShowOptions(!showOptions)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 16px',
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              color: 'var(--text-muted)',
              fontSize: '13px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            Not quite
            <ChevronRight size={14} style={{
              transform: showOptions ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.2s',
              color: 'var(--text-muted)',
            }} />
          </button>
        </div>
      )}

      {loading && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          padding: '12px',
          color: 'var(--text-muted)',
          fontSize: '13px',
        }}>
          <div style={{
            width: '16px',
            height: '16px',
            border: '2px solid var(--accent-primary-light)',
            borderTopColor: 'var(--accent-primary)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }} />
          Analyzing your data...
        </div>
      )}

      {/* Additional Options */}
      {showOptions && !loading && (
        <div style={{
          marginTop: '12px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
        }}>
          <button
            onClick={onEdit}
            style={{
              padding: '8px 12px',
              background: 'rgba(245, 158, 11, 0.2)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: '6px',
              color: '#f59e0b',
              fontSize: '12px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            ✏️ Edit my question
          </button>

          <button
            onClick={onCancel}
            style={{
              padding: '8px 12px',
              background: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '6px',
              color: '#ef4444',
              fontSize: '12px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            ✕ Cancel
          </button>
        </div>
      )}

      <style>{`
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
};

export default ClarificationCard;
