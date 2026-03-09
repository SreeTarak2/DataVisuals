import React from 'react';
import { useScroll, useSpring, useReducedMotion, motion } from 'framer-motion';

import Navbar from '../../components/landing/Navbar';
import HeroSection from '../../components/landing/HeroSection';
import TrustedBy from '../../components/landing/TrustedBy';
import FeatureBento from '../../components/landing/FeatureBento';
import InteractiveDemo from '../../components/landing/InteractiveDemo';
import HowItWorks from '../../components/landing/HowItWorks';
import AdvancedCapabilities from '../../components/landing/AdvancedCapabilities';
import UseCases from '../../components/landing/UseCases';
import TestimonialsCarousel from '../../components/landing/TestimonialsCarousel';
import PricingSection from '../../components/landing/PricingSection';
import FAQSection from '../../components/landing/FAQSection';
import CTASection from '../../components/landing/CTASection';
import Footer from '../../components/landing/Footer';

const LandingPage = () => {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="bg-[#020617] min-h-screen text-slate-50 selection:bg-slate-800 selection:text-white relative font-sans">
      {/* Structural Background Pattern */}
      <div className="bg-grid-pattern"></div>

      {/* Scroll Progress Bar */}
      {!prefersReducedMotion && (
        <motion.div
          className="fixed top-0 left-0 right-0 h-0.5 bg-sky-400 origin-left z-[100]"
          style={{ scaleX }}
          aria-hidden="true"
        />
      )}

      <Navbar />

      <main className="relative z-10">
        <HeroSection />
        <TrustedBy />
        <FeatureBento />
        <InteractiveDemo />
        <HowItWorks />
        <AdvancedCapabilities />
        <UseCases />
        <TestimonialsCarousel />
        <PricingSection />
        <FAQSection />
        <CTASection />
      </main>

      <Footer />
    </div>
  );
};

export default LandingPage;
