import React from 'react';

const Logo = ({ className = '', size = 32, showText = false }) => {
  return (
    <div className={`logo-container ${className}`} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <img 
        src="/logo.png?v=2" 
        alt="Signal Logo" 
        style={{ 
          width: `${size}px`, 
          height: `${size}px`, 
          objectFit: 'contain', 
          flexShrink: 0 
        }} 
      />
      
      {showText && (
        <span style={{ 
          fontSize: '18px', 
          fontWeight: '700', 
          letterSpacing: '-0.03em',
          background: 'linear-gradient(to bottom, #ffffff 40%, #a5a5a5 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          fontFamily: '"Space Grotesk", "Inter", system-ui, -apple-system, sans-serif'
        }}>
          Signal
        </span>
      )}
    </div>
  );
};

export default Logo;
