import React from 'react';
import { motion } from 'framer-motion';
import { cn } from "@/lib/utils";

const TactileButton = React.forwardRef(({
    children,
    className,
    variant = 'primary',
    size = 'default',
    ...props
}, ref) => {
    const variants = {
        primary: "bg-slate-ink text-cloud-white clay-button border border-white/5",
        secondary: "bg-white text-slate-900 clay-button border border-white/20 shadow-lg hover:shadow-xl hover:bg-slate-50 active:bg-white",
        ghost: "hover:bg-white/5 text-cloud-white/80 hover:text-cloud-white transition-colors",
    };

    const sizes = {
        default: "px-6 py-2.5 text-sm font-semibold rounded-xl",
        sm: "px-4 py-1.5 text-xs font-semibold rounded-lg",
        lg: "px-8 py-3.5 text-base font-bold rounded-2xl",
    };

    return (
        <motion.button
            ref={ref}
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98, y: 0 }}
            className={cn(
                "relative overflow-hidden inline-flex items-center justify-center transition-all duration-200 font-inter-tight tracking-tight",
                variants[variant],
                sizes[size],
                className
            )}
            {...props}
        >
            {/* Subtle Glow Effect */}
            <motion.div
                className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0"
                whileHover={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
            />
            <span className="relative z-10">{children}</span>
        </motion.button>
    );
});

TactileButton.displayName = "TactileButton";

export default TactileButton;
