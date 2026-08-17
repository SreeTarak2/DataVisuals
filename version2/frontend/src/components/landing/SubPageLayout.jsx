import React from 'react';
import Navbar from '@/components/layout/Navbar';
import { Footer } from './Footer';

import '@/assets/styles/landing-page.css';

/**
 * Shared shell for marketing sub-pages (/features, /pricing, /docs, /blog, /demo).
 */
const SubPageLayout = ({ children }) => {
  return (
    <div className="lp-root lp-container bg-[#0A0A0A] text-white min-h-screen selection:bg-[rgba(249,115,22,0.3)] selection:text-white">
      <Navbar />
      <main>{children}</main>
      <Footer />
    </div>
  );
};

export default SubPageLayout;
