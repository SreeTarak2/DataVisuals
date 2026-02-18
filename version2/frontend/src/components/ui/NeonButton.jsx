import React from 'react';
import { motion } from 'framer-motion';

const NeonButton = ({ children, className, variant = 'primary', ...props }) => {
    const baseStyles = "relative px-6 py-3 rounded-lg font-bold uppercase tracking-widest text-sm transition-all duration-300 overflow-hidden group";

    const variants = {
        primary: "bg-ocean/20 text-ocean border border-ocean/50 hover:bg-ocean hover:text-noir hover:shadow-[0_0_20px_rgba(91,136,178,0.6)]",
        secondary: "bg-midnight/40 text-pearl border border-midnight hover:border-pearl/50 hover:text-white hover:shadow-[0_0_15px_rgba(251,249,228,0.2)]",
        danger: "bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500 hover:text-white hover:shadow-[0_0_20px_rgba(239,68,68,0.5)]"
    };

    return (
        <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={`${baseStyles} ${variants[variant]} ${className || ''}`}
            {...props}
        >
            <span className="relative z-10 flex items-center gap-2 justify-center">
                {children}
            </span>

            {/* Scanline effect on hover */}
            <div className="absolute inset-0 bg-white/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out pointer-events-none" />
        </motion.button>
    );
};

export default NeonButton;
