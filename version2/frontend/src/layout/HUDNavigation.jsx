import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, BarChart2, MessageSquare, Settings, UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils'; // Assuming cn exists or I should create it. I will create it next if missing.

const HUDNavigation = () => {
    const navItems = [
        { icon: Home, label: 'CMD', path: '/dashboard' },
        { icon: UploadCloud, label: 'DATA', path: '/datasets' },
        { icon: MessageSquare, label: 'COMM', path: '/chat' },
        { icon: Box, label: 'VIZ', path: '/analysis' }, // Placeholder icon if Box not available, using simple div
        { icon: Settings, label: 'SYS', path: '/settings' },
    ];

    // Helper for NavLink classes
    const getNavLinkClass = ({ isActive }) => {
        return `
      relative group flex flex-col items-center justify-center w-16 h-16 rounded-xl transition-all duration-300
      ${isActive
                ? 'bg-ocean/20 text-ocean shadow-[0_0_15px_rgba(91,136,178,0.3)] border border-ocean/50'
                : 'text-muted-foreground hover:text-pearl hover:bg-midnight/40'
            }
    `;
    };

    return (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50">
            <div className="glass-panel px-4 py-2 flex items-center gap-2 border-pearl/20">
                {navItems.map((item) => (
                    <NavLink key={item.path} to={item.path} className={getNavLinkClass}>
                        {({ isActive }) => (
                            <>
                                <item.icon className={`w-6 h-6 ${isActive ? 'animate-pulse' : ''}`} />
                                <span className="text-[10px] font-bold mt-1 tracking-widest">{item.label}</span>

                                {/* Active Indicator Dot */}
                                {isActive && (
                                    <div className="absolute -bottom-1 w-1 h-1 bg-ocean rounded-full shadow-[0_0_5px_#5B88B2]" />
                                )}
                            </>
                        )}
                    </NavLink>
                ))}
            </div>
        </div>
    );
};

// Simple Fallback Icon
const Box = ({ className }) => (
    <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
    >
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
);

export default HUDNavigation;
