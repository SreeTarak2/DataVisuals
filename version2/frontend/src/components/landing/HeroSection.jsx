import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Play, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

import heroBg from '../../assets/landing/hero-bg.png';
import dashboardMockup from '../../assets/landing/dashboard-mockup.png';

const HeroSection = () => {
    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-slate-950 pt-20">
            {/* Background with Overlay */}
            <div className="absolute inset-0 z-0">
                <img
                    src={heroBg}
                    alt="Data Background"
                    className="w-full h-full object-cover opacity-40"
                />
                <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-950/50 to-slate-950"></div>
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-950/0 to-slate-950/0"></div>
            </div>

            <div className="container mx-auto px-4 z-10 relative">
                <div className="flex flex-col items-center text-center max-w-5xl mx-auto">

                    {/* Badge */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium mb-8 backdrop-blur-sm"
                    >
                        <Sparkles className="w-4 h-4" />
                        <span>AI-Powered Data Analysis for Everyone</span>
                    </motion.div>

                    {/* Heading */}
                    <motion.h1
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-5xl md:text-7xl font-bold text-white mb-6 tracking-tight leading-tight"
                    >
                        Your Personal <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">Data Analyst</span>
                        <br /> available 24/7.
                    </motion.h1>

                    {/* Subheading */}
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="text-lg md:text-xl text-slate-300 mb-10 max-w-2xl leading-relaxed"
                    >
                        Upload your data and let our AI agents analyze, visualize, and find insights for you.
                        Zero setup. <span className="text-white font-semibold">100% Free.</span>
                    </motion.p>

                    {/* CTA Buttons */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.3 }}
                        className="flex flex-col sm:flex-row gap-4 w-full justify-center mb-16"
                    >
                        <Link
                            to="/register"
                            className="group relative inline-flex items-center justify-center px-8 py-4 text-lg font-bold text-white transition-all duration-200 bg-blue-600 rounded-full hover:bg-blue-500 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-600 focus:ring-offset-slate-900"
                        >
                            Get Started Free
                            <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            <div className="absolute inset-0 rounded-full ring-2 ring-white/20 group-hover:ring-white/40 transition-all"></div>
                        </Link>

                        <button className="inline-flex items-center justify-center px-8 py-4 text-lg font-bold text-slate-300 transition-all duration-200 bg-white/5 border border-white/10 rounded-full hover:bg-white/10 hover:text-white backdrop-blur-sm">
                            <Play className="mr-2 w-5 h-5 fill-current" />
                            Watch Demo
                        </button>
                    </motion.div>

                    {/* Dashboard Preview Mockup */}
                    <motion.div
                        initial={{ opacity: 0, y: 40, rotateX: 10 }}
                        animate={{ opacity: 1, y: 0, rotateX: 0 }}
                        transition={{ duration: 0.8, delay: 0.4, type: "spring" }}
                        className="relative w-full max-w-5xl mx-auto"
                        style={{ perspective: '1000px' }}
                    >
                        <div className="relative rounded-xl overflow-hidden shadow-2xl border border-slate-700/50 bg-slate-900/50 backdrop-blur-xl group">
                            <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

                            {/* Browser Bar (Optional decoration) */}
                            <div className="h-8 bg-slate-800/80 flex items-center px-4 gap-2 border-b border-white/5">
                                <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                                <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                                <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                                <div className="ml-4 h-4 w-64 bg-slate-700/50 rounded-full blur-[1px]"></div>
                            </div>

                            <img
                                src={dashboardMockup}
                                alt="Dashboard Preview"
                                className="w-full h-auto transform transition-transform duration-700 hover:scale-[1.01]"
                            />

                            {/* Reflection/Shine effect */}
                            <div className="absolute inset-0 bg-gradient-to-tr from-white/5 to-transparent pointer-events-none"></div>
                        </div>

                        {/* Floating Elements (Decoration) */}
                        <motion.div
                            animate={{ y: [0, -20, 0] }}
                            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                            className="absolute -top-10 -right-10 w-24 h-24 bg-blue-500/20 rounded-full blur-3xl"
                        ></motion.div>
                        <motion.div
                            animate={{ y: [0, 20, 0] }}
                            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 1 }}
                            className="absolute -bottom-10 -left-10 w-32 h-32 bg-purple-500/20 rounded-full blur-3xl"
                        ></motion.div>
                    </motion.div>

                </div>
            </div>
        </section>
    );
};

export default HeroSection;
