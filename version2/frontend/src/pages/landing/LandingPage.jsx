import React from 'react';
import { motion, useScroll, useSpring, useReducedMotion } from 'framer-motion';

import Navbar from '@/components/layout/Navbar';
import HeroSection from '@/components/landing/HeroSection';
import TrustedBy from '@/components/landing/TrustedBy';
import FeatureBento from '@/components/landing/FeatureBento';
import HowItWorks from '@/components/landing/HowItWorks';
import AdvancedCapabilities from '@/components/landing/AdvancedCapabilities';
import InteractiveDemo from '@/components/landing/InteractiveDemo';
import TestimonialsCarousel from '@/components/landing/TestimonialsCarousel';
import PricingSection from '@/components/landing/PricingSection';
import FAQSection from '@/components/landing/FAQSection';
import { Footer } from '@/components/landing/Footer';

import './Landing.css';
import '@/assets/styles/landing-page.css';

function LandingPage() {
  const prefersReducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 28, restDelta: 0.001 });

  return (
    <div className="landing-premium bg-[#0A0A0A] text-white min-h-screen selection:bg-[var(--accent-primary)]/30 selection:text-white">
      {/* Scroll Progress Indicator */}
      {!prefersReducedMotion && (
        <motion.div 
          style={{ scaleX, transformOrigin: '0 0' }} 
          className="fixed top-0 left-0 right-0 h-[2px] bg-[var(--accent-primary)] z-[200]" 
        />
      )}

      <Navbar />

      <main>
        <HeroSection />
        <TrustedBy />
        <FeatureBento />
        <HowItWorks />
        <AdvancedCapabilities />
        <InteractiveDemo />
        <TestimonialsCarousel />
        <PricingSection />
        <FAQSection />
      </main>

      <Footer />
    </div>
  );
}

export default LandingPage;
