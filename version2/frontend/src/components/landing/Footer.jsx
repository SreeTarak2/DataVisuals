import React from 'react';
import { Link } from 'react-router-dom';
import Logo from '../common/Logo';
import { Github, Twitter, Linkedin, ArrowRight } from 'lucide-react';

export const Footer = () => {
  return (
    <footer className="w-full bg-[#0A0A0A] border-t border-white/[0.04] pt-16 pb-12 text-[var(--text-primary)]">
      <div className="lp-wrapper flex flex-col gap-y-8">
        
        {/* Final CTA Section */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-[#1E1E22] to-[#121215] border border-white/[0.08] p-10 md:p-16 text-center shadow-[0_24px_80px_-20px_rgba(0,0,0,0.8)] backdrop-blur-md">
          {/* Dual Radial Glows (Convergence and Signal Focus) */}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(249,115,22,0.12),transparent_50%)] pointer-events-none" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_100%_100%,rgba(59,130,246,0.03),transparent_35%)] pointer-events-none" />
          
          <div className="relative z-10 max-w-2xl mx-auto">
            <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white mb-4 leading-tight">
              Ready to turn data into understanding?
            </h2>
            <p className="text-sm md:text-base text-[var(--text-secondary)] mb-8 leading-relaxed max-w-lg mx-auto">
              Connect your data, build context, and uncover insights with Signal.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link 
                to="/register" 
                className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white font-semibold text-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_0_30px_rgba(249,115,22,0.25)]"
              >
                Start Free
                <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform duration-300" />
              </Link>
              <Link 
                to="/login" 
                className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.18] text-white font-semibold text-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_10px_20px_rgba(0,0,0,0.2)]"
              >
                Book Demo
              </Link>
            </div>
          </div>
        </div>

        {/* Footer Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-x-12 gap-y-8 py-4">
          {/* Column 1: Brand & Logo */}
          <div className="col-span-2 md:col-span-4 lg:col-span-1 flex flex-col justify-between gap-6">
            <div>
              <Link to="/" className="inline-block mb-4">
                <Logo size={24} showText={true} />
              </Link>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-6 max-w-[240px]">
                Transforming scattered data into clear, unified understanding.
              </p>
            </div>
            
            {/* Social Links */}
            <div className="flex items-center gap-3 text-[var(--text-muted)]">
              <a 
                href="https://twitter.com" 
                target="_blank" 
                rel="noreferrer" 
                className="w-8 h-8 rounded-full border border-white/[0.05] flex items-center justify-center text-neutral-400 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all duration-300"
                aria-label="Twitter / X"
              >
                <Twitter size={14} />
              </a>
              <a 
                href="https://github.com" 
                target="_blank" 
                rel="noreferrer" 
                className="w-8 h-8 rounded-full border border-white/[0.05] flex items-center justify-center text-neutral-400 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all duration-300"
                aria-label="GitHub"
              >
                <Github size={14} />
              </a>
              <a 
                href="https://linkedin.com" 
                target="_blank" 
                rel="noreferrer" 
                className="w-8 h-8 rounded-full border border-white/[0.05] flex items-center justify-center text-neutral-400 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all duration-300"
                aria-label="LinkedIn"
              >
                <Linkedin size={14} />
              </a>
            </div>
          </div>

          {/* Column 2: Product */}
          <div>
            <h4 className="text-[11px] font-bold text-white uppercase tracking-[0.15em] mb-5">Product</h4>
            <ul className="space-y-3.5 text-xs">
              <li><Link to="/#features" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Features</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">AI Chat</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Analysis</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Integrations</Link></li>
              <li><Link to="/#pricing" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Pricing</Link></li>
            </ul>
          </div>

          {/* Column 3: Resources */}
          <div>
            <h4 className="text-[11px] font-bold text-white uppercase tracking-[0.15em] mb-5">Resources</h4>
            <ul className="space-y-3.5 text-xs">
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Docs</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Blog</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Guides</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">API</Link></li>
            </ul>
          </div>

          {/* Column 4: Company */}
          <div>
            <h4 className="text-[11px] font-bold text-white uppercase tracking-[0.15em] mb-5">Company</h4>
            <ul className="space-y-3.5 text-xs">
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">About</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Careers</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Contact</Link></li>
            </ul>
          </div>

          {/* Column 5: Legal */}
          <div>
            <h4 className="text-[11px] font-bold text-white uppercase tracking-[0.15em] mb-5">Legal</h4>
            <ul className="space-y-3.5 text-xs">
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Privacy</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Terms</Link></li>
              <li><Link to="/register" className="text-[var(--text-secondary)] hover:text-white transition-all duration-200 hover:translate-x-0.5 inline-block">Security</Link></li>
            </ul>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="pt-8 border-t border-white/[0.04] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[var(--text-muted)] mt-4">
          <p>© {new Date().getFullYear()} Signal Inc. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link to="/register" className="hover:text-white transition-colors duration-200">Privacy Policy</Link>
            <Link to="/register" className="hover:text-white transition-colors duration-200">Terms of Service</Link>
          </div>
        </div>

      </div>
    </footer>
  );
};
