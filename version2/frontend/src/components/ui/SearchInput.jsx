import React from 'react';
import { Search } from 'lucide-react';
import { useTheme } from '../../store/themeStore';

export const SearchInput = ({
  placeholder = "Search...",
  value,
  onChange,
  className = "",
  style = {},
  width = 240,
  ...props
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const baseBorderColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)';

  return (
    <div className={`relative ${className}`} style={{ width: typeof width === 'number' ? `${width}px` : width }}>
      <Search
        className="w-3.5 h-3.5"
        style={{
          position: 'absolute',
          left: '10px',
          top: '50%',
          transform: 'translateY(-50%)',
          color: isDark ? 'rgba(255, 255, 255, 0.4)' : 'rgba(0, 0, 0, 0.4)',
          pointerEvents: 'none',
        }}
      />
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        style={{
          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
          border: `1px solid ${baseBorderColor}`,
          color: isDark ? 'white' : '#111827',
          width: '100%',
          outline: 'none',
          paddingLeft: '32px',
          paddingRight: '12px',
          paddingTop: '6px',
          paddingBottom: '6px',
          fontSize: '12px',
          borderRadius: '8px',
          transition: 'all 0.15s ease',
          ...style,
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = 'var(--accent-primary, #f97316)';
          e.currentTarget.style.boxShadow = '0 0 10px rgba(249,115,22,0.1)';
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = baseBorderColor;
          e.currentTarget.style.boxShadow = 'none';
        }}
        {...props}
      />
    </div>
  );
};

export default SearchInput;
