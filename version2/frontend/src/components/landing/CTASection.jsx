import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

const CTASection = () => {
    return (
        <section className="py-32 bg-[#020617] relative border-t border-slate-900 border-b overflow-hidden">
            {/* Animated background layer */}
            <div className="absolute inset-0 z-0 pointer-events-none">
                <motion.div
                    animate={{
                        opacity: [0.1, 0.3, 0.1],
                        scale: [1, 1.2, 1]
                    }}
                    transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-sky-500/20 blur-[120px] rounded-full"
                />
            </div>
            <div className="container mx-auto px-6 max-w-4xl text-center relative z-10">
                <motion.h2
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-4xl md:text-5xl font-bold text-slate-50 mb-6 tracking-tight text-balance"
                >
                    Start analyzing your data today.
                </motion.h2>
                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="text-slate-400 text-lg md:text-xl mb-10 max-w-2xl mx-auto text-balance"
                >
                    Join 10,000+ analysts who have stopped writing boilerplate SQL and started delivering insights faster.
                </motion.p>

                <div className="flex flex-col items-center gap-6">
                    <Link
                        to="/register"
                        className="btn-primary inline-flex items-center justify-center px-8 py-4 text-base focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none"
                    >
                        Start Free Trial
                        <ArrowRight className="ml-3 w-5 h-5" aria-hidden="true" />
                    </Link>

                    <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-8 text-sm text-slate-500">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-slate-600" aria-hidden="true" />
                            <span>14-day free trial</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-slate-600" aria-hidden="true" />
                            <span>No credit card required</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-slate-600" aria-hidden="true" />
                            <span>Cancel anytime</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default CTASection;
