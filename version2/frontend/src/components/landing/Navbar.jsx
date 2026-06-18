import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Menu, X, ChevronDown, ArrowRight, Zap, Users, Box, Cpu 
} from 'lucide-react';
import Logo from '../common/Logo';
import '../layout/Navbar/Navbar.css';

const productItems = [
  { icon: Zap, label: 'Features', desc: 'AI insights & auto dashboards.', href: '/features' },
  { icon: Cpu, label: 'How it works', desc: 'Upload, ask, and share in 3 steps.', href: '/how-it-works' },
  { icon: Users, label: 'Use cases', desc: 'For analysts & product teams.', href: '/use-cases' },
  { icon: Box, label: 'Integrations', desc: 'CSV, Excel, Sheets, & more.', href: '/integrations' }
];

export const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  
  const location = useLocation();
  const dropdownRef = useRef(null);
  const productButtonRef = useRef(null);

  // Scroll Detection
  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [location.pathname]);

  // Click outside logic for dropdowns
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) && 
          productButtonRef.current && !productButtonRef.current.contains(e.target)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <>
      <header className={`navbar-wrapper ${isScrolled ? 'scrolled' : ''}`}>
        <div className="navbar-container">
          {/* Logo Section */}
          <Link to="/" className="nav-logo">
            <Logo size={32} showText={true} />
          </Link>

          {/* Desktop Links */}
          <nav className="nav-main-links">
            <div 
              className="nav-dropdown-wrapper"
              onMouseEnter={() => setActiveDropdown('product')}
              onMouseLeave={() => setActiveDropdown(null)}
            >
              <button 
                ref={productButtonRef}
                className={`nav-link-item ${activeDropdown === 'product' ? 'active' : ''}`}
              >
                Product
                <ChevronDown size={14} className="nav-chevron" />
              </button>

              <AnimatePresence>
                {activeDropdown === 'product' && (
                  <motion.div
                    ref={dropdownRef}
                    initial={{ opacity: 0, y: 8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 8, scale: 0.98 }}
                    transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
                    className="dropdown-menu"
                  >
                    <div className="mega-menu-inner">
                      <div className="mega-spotlight">
                        <div className="spotlight-tag">Platform</div>
                        <h4 className="spotlight-title">Signal Intelligence</h4>
                        <p className="spotlight-desc">The first context-aware AI built for serious data teams.</p>
                        <Link to="/features" className="spotlight-link">
                          View all features <ArrowRight size={14} />
                        </Link>
                      </div>

                      <div className="mega-links">
                        <div className="dropdown-grid">
                          {productItems.map(item => (
                            <Link key={item.label} to={item.href} className="dropdown-item">
                              <div className="dropdown-icon-wrapper">
                                <item.icon size={18} />
                              </div>
                              <div className="dropdown-content">
                                <span className="dropdown-label">{item.label}</span>
                                <span className="dropdown-desc">{item.desc}</span>
                              </div>
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <Link to="/pricing" className="nav-link-item">Pricing</Link>
            <Link to="/docs" className="nav-link-item">Docs</Link>
            <Link to="/blog" className="nav-link-item">Blog</Link>
          </nav>

          {/* Actions */}
          <div className="nav-actions">
            <Link to="/login" className="btn-signin">Sign in</Link>
            <Link to="/register" className="btn-start">
              Start free
              <div className="btn-arrow-circle">
                <ArrowRight size={12} />
              </div>
            </Link>
          </div>

          {/* Mobile Trigger */}
          <button className="mobile-trigger" onClick={() => setIsMobileOpen(!isMobileOpen)}>
            {isMobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Mobile Menu Panel */}
      <AnimatePresence>
        {isMobileOpen && (
          <motion.div
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
            className="mobile-panel"
          >
            <div className="mobile-card">
              <Link to="/features" className="mobile-nav-item">Features <ArrowRight size={18} /></Link>
              <Link to="/how-it-works" className="mobile-nav-item">How it works <ArrowRight size={18} /></Link>
              <Link to="/pricing" className="mobile-nav-item">Pricing <ArrowRight size={18} /></Link>
              <Link to="/docs" className="mobile-nav-item">Docs <ArrowRight size={18} /></Link>
            </div>

            <Link to="/register" style={{ textDecoration: 'none' }}>
              <div className="mobile-card mobile-card-start">
                <span className="footer-label">Start for free</span>
                <div className="footer-avatar">
                  <ArrowRight size={20} />
                </div>
              </div>
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};
