/**
 * renderBold — Shared utility for rendering **bold** markdown syntax in JSX.
 * 
 * Replaces **text** patterns with <strong> tags while preserving
 * the rest of the string as plain text.
 */
import React from 'react';

export const renderBold = (text) => {
    if (!text) return '';
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
        }
        return <span key={i}>{part}</span>;
    });
};
