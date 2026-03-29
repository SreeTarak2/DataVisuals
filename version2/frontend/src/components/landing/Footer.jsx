import React from 'react';
import { Github, Twitter, Linkedin, Database } from 'lucide-react';
import { Link } from 'react-router-dom';

const Footer = () => {
    return (
        <footer className="bg-[#0A0A0A] pt-20 pb-12 overflow-hidden border-t border-white/[0.03]">
            <div className="container mx-auto px-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
                    <div className="md:col-span-1">
                        <Link to="/" className="flex items-center gap-3 group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded-sm w-fit mb-6">
                            <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center text-white shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                                <Database className="w-5 h-5" aria-hidden="true" />
                            </div>
                            <span className="text-xl font-bold text-white tracking-tight">DataSage</span>
                        </Link>
                        <p className="text-neutral-400 text-sm mb-6 max-w-xs text-balance">
                            The intelligent data workspace for modern teams.
                        </p>
                        <div className="flex items-center gap-5">
                            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-neutral-500 hover:text-white transition-colors" aria-label="Visit our GitHub">
                                <Github className="w-5 h-5" aria-hidden="true" />
                            </a>
                            <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="text-neutral-500 hover:text-white transition-colors" aria-label="Visit our Twitter">
                                <Twitter className="w-5 h-5" aria-hidden="true" />
                            </a>
                            <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="text-neutral-500 hover:text-white transition-colors" aria-label="Visit our LinkedIn">
                                <Linkedin className="w-5 h-5" aria-hidden="true" />
                            </a>
                        </div>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-6">Product</h4>
                        <ul className="space-y-4">
                            <li><Link to="/features" className="text-neutral-400 hover:text-white text-sm transition-colors">Features</Link></li>
                            <li><Link to="/integrations" className="text-neutral-400 hover:text-white text-sm transition-colors">Integrations</Link></li>
                            <li><Link to="/pricing" className="text-neutral-400 hover:text-white text-sm transition-colors">Pricing</Link></li>
                            <li><Link to="/changelog" className="text-neutral-400 hover:text-white text-sm transition-colors">Changelog</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-6">Resources</h4>
                        <ul className="space-y-4">
                            <li><Link to="/docs" className="text-neutral-400 hover:text-white text-sm transition-colors">Documentation</Link></li>
                            <li><Link to="/blog" className="text-neutral-400 hover:text-white text-sm transition-colors">Blog</Link></li>
                            <li><Link to="/community" className="text-neutral-400 hover:text-white text-sm transition-colors">Community</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-6">Legal</h4>
                        <ul className="space-y-4">
                            <li><Link to="/privacy" className="text-neutral-400 hover:text-white text-sm transition-colors">Privacy Policy</Link></li>
                            <li><Link to="/terms" className="text-neutral-400 hover:text-white text-sm transition-colors">Terms of Service</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="pt-8 border-t border-white/[0.03] flex flex-col md:flex-row justify-between items-center gap-4">
                    <p className="text-neutral-500 text-xs tracking-widest uppercase">© {new Date().getFullYear()} DataSage Inc. Built with Precision.</p>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
