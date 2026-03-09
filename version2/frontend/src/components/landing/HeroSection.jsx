import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import heroIllustration from '../../assets/landing/hero-illustration.png';

const HeroSection = () => {
    const prefersReducedMotion = useReducedMotion();

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: prefersReducedMotion ? 0 : 0.08,
                ease: 'easeOut',
                duration: 0.3
            }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, y: prefersReducedMotion ? 0 : 20 },
        visible: {
            opacity: 1,
            y: 0,
            transition: {
                duration: 0.6,
                ease: [0.16, 1, 0.3, 1] // Apple-like gentle settle
            }
        }
    };

    return (
        <section className="relative min-h-[90vh] flex flex-col items-center pt-32 pb-0 overflow-hidden">
            {/* Ambient Background Glows */}
            <motion.div
                animate={{
                    scale: [1, 1.2, 1],
                    opacity: [0.3, 0.5, 0.3],
                }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                className="absolute top-[10%] left-[15%] w-[40vw] h-[40vw] max-w-[600px] max-h-[600px] bg-sky-500/20 rounded-full blur-[120px] pointer-events-none"
            />
            <motion.div
                animate={{
                    scale: [1, 1.3, 1],
                    opacity: [0.2, 0.4, 0.2],
                }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
                className="absolute top-[30%] right-[10%] w-[35vw] h-[35vw] max-w-[500px] max-h-[500px] bg-purple-500/20 rounded-full blur-[100px] pointer-events-none"
            />

            <div className="container mx-auto px-4 z-10 relative flex flex-col items-center text-center max-w-5xl">
                <motion.div
                    className="flex flex-col items-center text-center"
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                >
                    {/* Top Soft Badge */}
                    <motion.div variants={itemVariants} className="mb-6">
                        <Link to="/contact" className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-900/50 border border-slate-800 text-sm text-slate-300 hover:text-white hover:bg-slate-800 transition-colors focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none">
                            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></span>
                            Meet DataSage—AI for your data stack
                            <ArrowRight className="w-4 h-4 ml-1 opacity-70" aria-hidden="true" />
                        </Link>
                    </motion.div>

                    {/* High-Conversion Outcome Headline */}
                    <motion.h1
                        variants={itemVariants}
                        className="text-6xl md:text-8xl font-bold text-slate-50 mb-8 tracking-tighter text-balance leading-none"
                    >
                        Turn raw data into executive dashboards.
                    </motion.h1>

                    {/* Specific Subheadline */}
                    <motion.p
                        variants={itemVariants}
                        className="text-xl md:text-2xl text-slate-400 mb-12 max-w-3xl text-balance font-light"
                    >
                        Stop writing SQL for basic questions. Upload your CSV or connect your database, and let the engine instantly generate professional, interactive charts.
                    </motion.p>

                    {/* Primary CTA */}
                    <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center w-full justify-center gap-4 mb-20">
                        <Link
                            to="/register"
                            className="bg-slate-50 text-slate-950 hover:bg-white inline-flex items-center justify-center px-8 py-4 text-base font-semibold rounded-full transition-all focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none shadow-[0_0_40px_-10px_rgba(255,255,255,0.3)] hover:shadow-[0_0_50px_-10px_rgba(255,255,255,0.5)] transform hover:-translate-y-0.5"
                        >
                            Start Free Trial
                            <ArrowRight className="ml-3 w-5 h-5 group-hover:translate-x-1" aria-hidden="true" />
                        </Link>

                        <Link
                            to="/demo"
                            className="bg-transparent text-slate-300 hover:text-white inline-flex items-center justify-center px-8 py-4 text-base font-medium rounded-full transition-all focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none"
                        >
                            Book a Demo
                        </Link>
                    </motion.div>

                    {/* Expansive Abstract Graphic (No harsh borders) */}
                    <motion.div
                        variants={itemVariants}
                        className="w-full relative px-4"
                    >
                        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#020617] to-transparent z-10 pointer-events-none"></div>
                        <img
                            src={heroIllustration}
                            alt="Abstract illustration of data processing and clarity"
                            width={1400}
                            height={800}
                            decoding="async"
                            fetchPriority="high"
                            className="w-full h-auto max-w-6xl mx-auto object-cover opacity-80"
                            style={{
                                maskImage: 'linear-gradient(to bottom, black 60%, transparent 100%)',
                                WebkitMaskImage: 'linear-gradient(to bottom, black 60%, transparent 100%)'
                            }}
                        />
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
};

export default HeroSection;
