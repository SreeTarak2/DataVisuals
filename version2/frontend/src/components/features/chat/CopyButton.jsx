/**
 * CopyButton — Text copy with checkmark feedback
 *
 * Click to copy text to clipboard. Shows a checkmark icon
 * for 1.5 seconds after copying, then reverts to the copy icon.
 */
import React, { useState, memo } from 'react';
import { Copy, Check } from 'lucide-react';

const CopyButton = memo(({ text, size = 13 }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={handleCopy} className="chat-action-btn" title={copied ? 'Copied!' : 'Copy'}>
      {copied ? <Check size={size} className="text-ocean" /> : <Copy size={size} />}
    </button>
  );
});

CopyButton.displayName = 'CopyButton';

export default CopyButton;
