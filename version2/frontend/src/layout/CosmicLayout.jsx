import React from 'react';
import ParticleBackground from '@/components/ui/ParticleBackground';
import HUDNavigation from './HUDNavigation';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';

const CosmicLayout = () => {
    const location = useLocation();

    // Routes where navigation should be hidden (e.g., Login)
    const hideNav = ['/login', '/register', '/'].includes(location.pathname);

    return (
        <div className="relative min-h-screen w-full overflow-hidden bg-noir text-pearl font-sans selection:bg-ocean/30 selection:text-white">
            <ParticleBackground />

            <main className="relative z-10 w-full h-full">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={location.pathname}
                        initial={{ opacity: 0, scale: 0.98, filter: 'blur(10px)' }}
                        animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, scale: 1.02, filter: 'blur(10px)' }}
                        transition={{ duration: 0.4, ease: "circOut" }}
                        className="w-full h-full"
                    >
                        <Outlet />
                    </motion.div>
                </AnimatePresence>
            </main>

            {!hideNav && <HUDNavigation />}
        </div>
    );
};

export default CosmicLayout;
