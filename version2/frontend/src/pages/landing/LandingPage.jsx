import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useSpring, useReducedMotion } from 'framer-motion';
import { Database, Menu, X } from 'lucide-react';

import HeroSection from '../../components/landing/HeroSection';
import TrustedBy from '../../components/landing/TrustedBy';
import FeatureBento from '../../components/landing/FeatureBento';
import HowItWorks from '../../components/landing/HowItWorks';
import UseCases from '../../components/landing/UseCases';
import CTASection from '../../components/landing/CTASection';
import Footer from '../../components/landing/Footer';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      <motion.nav
        initial={{ y: prefersReducedMotion ? 0 : -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? 'glass-nav py-4' : 'py-6 bg-transparent'
          }`}
      >
        <div className="container mx-auto px-6 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-3 group focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none rounded-sm">
            <div className="w-8 h-8 bg-slate-50 flex items-center justify-center text-slate-950">
              <Database className="w-4 h-4 fill-current" aria-hidden="true" />
            </div>
            <span className="text-xl font-bold text-slate-50 tracking-tight">DataSage</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            {['Features', 'How it Works', 'Use Cases', 'Pricing'].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase().replace(/\\s+/g, '-')}`}
                className="nav-link text-sm font-medium focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none rounded-sm px-1 py-0.5"
              >
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-6">
            <Link
              to="/login"
              className="text-sm font-medium text-slate-400 hover:text-slate-50 transition-colors focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none rounded-sm px-2 py-1"
            >
              Log In
            </Link>
            <Link
              to="/register"
              className="btn-primary px-5 py-2 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none outline-none"
            >
              Start Free Trial
            </Link>
          </div>

          <button
            className="md:hidden text-slate-50 p-2 focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={isMobileMenuOpen}
          >
            {isMobileMenuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </motion.nav>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <motion.div
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className="fixed inset-0 z-40 bg-slate-950 pt-24 px-6 md:hidden border-b border-white/5"
        >
          <div className="flex flex-col gap-6 text-lg">
            {['Features', 'How it Works', 'Use Cases', 'Pricing'].map((item) => (
              <a
                key={item}
                href={`#${item.toLowerCase().replace(/\\s+/g, '-')}`}
                className="text-slate-400 hover:text-slate-50 font-medium"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {item}
              </a>
            ))}
            <div className="h-px bg-white/5 my-4"></div>
            <Link to="/login" className="text-slate-400 hover:text-slate-50 font-medium" onClick={() => setIsMobileMenuOpen(false)}>Log in</Link>
            <Link to="/register" className="text-slate-50 font-medium" onClick={() => setIsMobileMenuOpen(false)}>Start Free Trial</Link>
          </div>
        </motion.div>
      )}
    </>
  );
};

const LandingPage = () => {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="bg-[#020617] min-h-screen text-slate-50 selection:bg-slate-800 selection:text-white relative">
      {/* Structural Background Pattern */}
      <div className="bg-grid-pattern"></div>

      {/* Scroll Progress Bar */}
      {!prefersReducedMotion && (
        <motion.div
          className="fixed top-0 left-0 right-0 h-0.5 bg-slate-50 origin-left z-[100]"
          style={{ scaleX }}
          aria-hidden="true"
        />
      )}

      <Navbar />

      <main className="relative z-10">
        <HeroSection />
        <TrustedBy />
        <FeatureBento />
        <HowItWorks />
        <UseCases />
        <CTASection />
      </main>

      <Footer />
    </div>
  );
};

export default LandingPage;
