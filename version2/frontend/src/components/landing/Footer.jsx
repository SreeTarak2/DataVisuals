import React from 'react';
import { Link } from 'react-router-dom';
import Logo from '../common/Logo';
import { ArrowRight } from 'lucide-react';

export const Footer = () => {
    return (
        <footer className="lp-footer text-[var(--text-primary)]">
            <div className="lp-wrapper flex flex-col gap-y-10">

                {/* Final CTA */}
                <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] p-10 md:p-16 text-center">
                    <div className="absolute inset-0 lp-glow-orange pointer-events-none" />
                    <div className="absolute inset-0 pointer-events-none"
                        style={{ background: 'radial-gradient(circle at 100% 100%, rgba(249,115,22,0.06), transparent 40%)' }} />

                    <div className="relative z-10 max-w-2xl mx-auto">
                        <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white mb-4 leading-tight text-balance">
                            Ready to stop re-explaining your data?
                        </h2>
                        <p className="text-sm md:text-base text-[var(--text-secondary)] mb-8 leading-relaxed max-w-lg mx-auto">
                            Connect your data, teach Signal once, and watch every answer get smarter.
                        </p>

                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Link
                                to="/register"
                                className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-white font-semibold text-sm transition-all duration-300 hover:-translate-y-0.5"
                                style={{ background: 'var(--accent-primary)', boxShadow: '0 8px 30px -8px rgba(249,115,22,0.5)' }}
                            >
                                Start free
                                <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform duration-300" />
                            </Link>
                            <Link
                                to="/demo"
                                className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.18] text-white font-semibold text-sm transition-all duration-300 hover:-translate-y-0.5"
                            >
                                Book a demo
                            </Link>
                        </div>
                    </div>
                </div>

                {/* Link grid */}
                <div className="lp-footer-grid py-4">
                    {/* Brand */}
                    <div className="flex flex-col justify-between gap-6">
                        <div>
                            <Link to="/" className="inline-block mb-4">
                                <Logo size={24} showText={true} />
                            </Link>
                            <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-[240px]">
                                Context-aware AI analytics. Every correction teaches the system; every insight compounds.
                            </p>
                        </div>
                    </div>

                    {/* Product */}
                    <div>
                        <h4>Product</h4>
                        <ul>
                            <li><Link to="/features">Features</Link></li>
                            <li><Link to="/pricing">Pricing</Link></li>
                            <li><Link to="/#how-it-works">How it works</Link></li>
                            <li><Link to="/demo">Book a demo</Link></li>
                        </ul>
                    </div>

                    {/* Resources */}
                    <div>
                        <h4>Resources</h4>
                        <ul>
                            <li><Link to="/docs">Docs</Link></li>
                            <li><Link to="/blog">Blog</Link></li>
                            <li><Link to="/docs#api">API reference</Link></li>
                            <li><Link to="/docs#security">Security</Link></li>
                        </ul>
                    </div>

                    {/* Get started */}
                    <div>
                        <h4>Get started</h4>
                        <ul>
                            <li><Link to="/register">Create account</Link></li>
                            <li><Link to="/login">Sign in</Link></li>
                            <li><Link to="/pricing">Plans</Link></li>
                        </ul>
                    </div>

                    {/* Legal */}
                    <div>
                        <h4>Legal</h4>
                        <ul>
                            <li><Link to="/docs#security">Privacy</Link></li>
                            <li><Link to="/docs#security">Terms</Link></li>
                            <li><Link to="/docs#security">Security</Link></li>
                        </ul>
                    </div>
                </div>

                {/* Bottom */}
                <div className="pt-8 border-t border-white/[0.04] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-neutral-500">
                    <p>© {new Date().getFullYear()} Signal. All rights reserved.</p>
                    <p className="font-mono text-[11px]">Built with DuckDB, ChromaDB &amp; OpenRouter</p>
                </div>
            </div>
        </footer>
    );
};
