import React from 'react';
import { Github, Twitter, Linkedin, Database } from 'lucide-react';
import { Link } from 'react-router-dom';

const Footer = () => {
    return (
        <footer className="bg-[#020617] pt-20 pb-12">
            <div className="container mx-auto px-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
                    <div className="md:col-span-1">
                        <Link to="/" className="flex items-center gap-3 group focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none rounded-sm w-fit mb-6">
                            <div className="w-8 h-8 bg-slate-50 flex items-center justify-center text-slate-950">
                                <Database className="w-4 h-4 fill-current" aria-hidden="true" />
                            </div>
                            <span className="text-xl font-bold text-slate-50 tracking-tight">DataSage</span>
                        </Link>
                        <p className="text-slate-400 text-sm mb-6 max-w-xs text-balance">
                            The intelligent data workspace for modern teams.
                        </p>
                        <div className="flex items-center gap-4">
                            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-50 transition-colors focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm" aria-label="Visit our GitHub">
                                <Github className="w-5 h-5" aria-hidden="true" />
                            </a>
                            <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-50 transition-colors focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm" aria-label="Visit our Twitter">
                                <Twitter className="w-5 h-5" aria-hidden="true" />
                            </a>
                            <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-50 transition-colors focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm" aria-label="Visit our LinkedIn">
                                <Linkedin className="w-5 h-5" aria-hidden="true" />
                            </a>
                        </div>
                    </div>

                    <div>
                        <h4 className="text-slate-50 font-semibold mb-6">Product</h4>
                        <ul className="space-y-4">
                            <li><Link to="/features" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Features</Link></li>
                            <li><Link to="/integrations" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Integrations</Link></li>
                            <li><Link to="/pricing" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Pricing</Link></li>
                            <li><Link to="/changelog" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Changelog</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-slate-50 font-semibold mb-6">Resources</h4>
                        <ul className="space-y-4">
                            <li><Link to="/docs" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Documentation</Link></li>
                            <li><Link to="/blog" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Blog</Link></li>
                            <li><Link to="/community" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Community</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-slate-50 font-semibold mb-6">Legal</h4>
                        <ul className="space-y-4">
                            <li><Link to="/privacy" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Privacy Policy</Link></li>
                            <li><Link to="/terms" className="text-slate-400 hover:text-slate-50 text-sm focus-visible:ring-2 focus-visible:ring-sky-400 rounded-sm outline-none">Terms of Service</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="pt-8 border-t border-slate-900 flex flex-col md:flex-row justify-between items-center gap-4">
                    <p className="text-slate-500 text-sm tabular-data">© {new Date().getFullYear()} DataSage Inc. All rights reserved.</p>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
