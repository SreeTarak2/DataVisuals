import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Menu, X, Sun, Moon } from 'lucide-react';
import { useTheme } from '@/store/themeStore';
import TactileButton from '@/components/ui/TactileButton';

const Navbar = () => {
    const [isScrolled, setIsScrolled] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const { theme, toggleTheme } = useTheme();

    useEffect(() => {
        const handleScroll = () => setIsScrolled(window.scrollY > 20);
        window.addEventListener('scroll', handleScroll, { passive: true });
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const navLinks = [
        { name: 'Features', href: '#features' },
        { name: 'Solutions', href: '#solutions' },
        { name: 'Enterprise', href: '#enterprise' },
        { name: 'Pricing', href: '#pricing' },
    ];

    return (
        <motion.nav
            initial={{ y: -100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${isScrolled
                ? 'py-3 bg-slate-ink/80 backdrop-blur-xl border-b border-white/5'
                : 'py-6 bg-transparent'
                }`}
        >
            <div className="container mx-auto px-6 flex justify-between items-center">
                {/* Brand Logo */}
                <Link to="/" className="flex items-center gap-3 group">
                    <motion.div
                        whileHover={{ rotate: 5, scale: 1.1 }}
                        className="w-10 h-10 bg-cloud-white flex items-center justify-center rounded-xl clay-button"
                    >
                        <Database className="w-5 h-5 text-slate-ink fill-current" />
                    </motion.div>
                    <span className="text-2xl font-black text-cloud-white tracking-tighter font-inter-tight">
                        Data<span className="text-cloud-white/60">Sage</span>
                    </span>
                </Link>

                {/* Desktop Navigation */}
                <div className="hidden lg:flex items-center gap-10">
                    <div className="flex items-center gap-8">
                        {navLinks.map((link) => (
                            <motion.a
                                key={link.name}
                                href={link.href}
                                whileHover={{ y: -2 }}
                                className="text-sm font-bold text-cloud-white/70 hover:text-cloud-white transition-colors font-inter-tight uppercase tracking-widest"
                            >
                                {link.name}
                            </motion.a>
                        ))}
                    </div>

                    <div className="h-6 w-px bg-white/10 mx-2" />

                    <div className="flex items-center gap-4">
                        <motion.button
                            onClick={toggleTheme}
                            whileTap={{ scale: 0.9 }}
                            className="p-2.5 rounded-full bg-white/5 text-cloud-white/80 hover:text-cloud-white hover:bg-white/10 transition-all clay-button border border-white/5"
                            aria-label="Toggle Theme"
                        >
                            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                        </motion.button>

                        <Link to="/login" className="text-sm font-bold text-cloud-white/70 hover:text-cloud-white px-4 py-2 font-inter-tight">
                            Sign In
                        </Link>

                        <TactileButton variant="primary" size="sm">
                            Get Started
                        </TactileButton>
                    </div>
                </div>

                {/* Mobile Menu Toggle */}
                <button
                    className="lg:hidden text-cloud-white p-2"
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                >
                    {isMobileMenuOpen ? <X size={28} /> : <Menu size={28} />}
                </button>
            </div>

            {/* Mobile Menu */}
            <AnimatePresence>
                {isMobileMenuOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="lg:hidden bg-slate-ink border-b border-white/5 overflow-hidden"
                    >
                        <div className="container mx-auto px-6 py-8 flex flex-col gap-6">
                            {navLinks.map((link) => (
                                <a
                                    key={link.name}
                                    href={link.href}
                                    className="text-xl font-bold text-cloud-white/80"
                                    onClick={() => setIsMobileMenuOpen(false)}
                                >
                                    {link.name}
                                </a>
                            ))}
                            <div className="h-px bg-white/5 w-full" />
                            <div className="flex flex-col gap-4">
                                <Link to="/login" className="text-lg font-bold text-cloud-white/80">
                                    Sign In
                                </Link>
                                <TactileButton variant="primary" className="w-full">
                                    Get Started
                                </TactileButton>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.nav>
    );
};

export default Navbar;
