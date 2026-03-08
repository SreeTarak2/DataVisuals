import React, { useRef, useState } from 'react';
import { motion, useMotionTemplate, useMotionValue, useSpring } from 'framer-motion';

const HolographicCard = ({ children, className }) => {
    const ref = useRef(null);
    const x = useMotionValue(0);
    const y = useMotionValue(0);

    const xSpring = useSpring(x);
    const ySpring = useSpring(y);

    const transform = useMotionTemplate`rotateX(${xSpring}deg) rotateY(${ySpring}deg)`;

    const handleMouseMove = (e) => {
        if (!ref.current) return;

        const rect = ref.current.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;

        const mouseX = (e.clientX - rect.left) * 32.5;
        const mouseY = (e.clientY - rect.top) * 32.5;

        const rX = (mouseY / height - 32.5 / 2) * -1;
        const rY = (mouseX / width - 32.5 / 2);

        x.set(rX);
        y.set(rY);
    };

    const handleMouseLeave = () => {
        x.set(0);
        y.set(0);
    };

    return (
        <motion.div
            ref={ref}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            style={{
                transformStyle: "preserve-3d",
                transform
            }}
            className={`relative group rounded-xl bg-midnight/30 border border-ocean/20 backdrop-blur-sm transition-all duration-200 hover:shadow-deep ${className || ''}`}
        >
            <div
                style={{ transform: "translateZ(50px)" }}
                className="relative z-10 h-full p-6 text-pearl"
            >
                {children}
            </div>

            {/* Holographic Gradient Overlay */}
            <div
                className="absolute inset-0 rounded-xl bg-gradient-to-br from-ocean/10 via-transparent to-midnight/50 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{ transform: "translateZ(25px)" }}
            />

            {/* Corner Accents */}
            <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-ocean/30 rounded-tl-xl opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-ocean/30 rounded-br-xl opacity-50 group-hover:opacity-100 transition-opacity" />
        </motion.div>
    );
};

export default HolographicCard;
