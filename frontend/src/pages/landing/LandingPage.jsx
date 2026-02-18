import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useSpring } from 'framer-motion';
import { Sparkles, Menu, X } from 'lucide-react';

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

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      <motion.nav
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? 'bg-slate-950/80 backdrop-blur-md border-b border-white/5 py-4' : 'py-6 bg-transparent'}`}
      >
        <div className="container mx-auto px-4 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <Sparkles className="w-5 h-5 fill-current" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">DataSage AI</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            {['Features', 'How it Works', 'Use Cases', 'Pricing'].map((item) => (
              <a key={item} href="#" className="text-sm font-medium text-slate-400 hover:text-white transition-colors">
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-4">
            <Link to="/auth/login" className="text-sm font-medium text-white hover:text-blue-400 transition-colors">
              Log in
            </Link>
            <Link
              to="/auth/register"
              className="px-5 py-2.5 rounded-full bg-white text-slate-950 text-sm font-bold hover:bg-blue-50 transition-colors shadow-lg shadow-white/10"
            >
              Get Started
            </Link>
          </div>

          <button className="md:hidden text-white" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
            {isMobileMenuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </motion.nav>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed inset-0 z-40 bg-slate-950 pt-24 px-6 md:hidden"
        >
          <div className="flex flex-col gap-6 text-lg">
            {['Features', 'How it Works', 'Use Cases', 'Pricing'].map((item) => (
              <a key={item} href="#" className="text-slate-400 hover:text-white font-medium">
                {item}
              </a>
            ))}
            <div className="h-px bg-white/10 my-4"></div>
            <Link to="/auth/login" className="text-white font-medium">Log in</Link>
            <Link to="/auth/register" className="text-blue-400 font-bold">Get Started</Link>
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

  return (
    <div className="bg-slate-950 min-h-screen text-slate-200 selection:bg-blue-500/30">
      {/* Scroll Progress Bar */}
      <motion.div
        className="fixed top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-cyan-400 origin-left z-[100]"
        style={{ scaleX }}
      />

      <Navbar />

      <main>
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