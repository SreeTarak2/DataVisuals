import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

const CTASection = () => {
    return (
        <section className="py-32 bg-[#0A0A0A] relative border-t border-white/[0.03] overflow-hidden">
            {/* Animated background layer */}
            <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
                <motion.div
                    animate={{
                        opacity: [0.05, 0.15, 0.05],
                        scale: [1, 1.2, 1]
                    }}
                    transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[500px] bg-blue-500/10 blur-[120px] rounded-full"
                />
            </div>
            <div className="container mx-auto px-6 max-w-4xl text-center relative z-10">
                <motion.h2
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8 }}
                    className="text-4xl md:text-6xl font-bold text-white mb-6 tracking-tight text-balance leading-[1.1]"
                >
                    Start analyzing your data today.
                </motion.h2>
                <motion.p
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, delay: 0.2 }}
                    className="text-neutral-400 text-lg md:text-xl mb-12 max-w-2xl mx-auto text-balance"
                >
                    Join 10,000+ analysts who have stopped writing boilerplate SQL and started delivering insights faster.
                </motion.p>

                <div className="flex flex-col items-center gap-10">
                    <Link
                        to="/register"
                        className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-10 rounded-2xl shadow-[0_0_40px_rgba(59,130,246,0.3)] transition-all duration-300 flex items-center group scale-100 hover:scale-105 active:scale-95"
                    >
                        Start Free Trial
                        <ArrowRight className="ml-3 w-5 h-5 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                    </Link>

                    <div className="flex flex-col sm:flex-row items-center gap-6 sm:gap-12 text-sm text-neutral-500">
                        <div className="flex items-center gap-3">
                            <CheckCircle2 className="w-4 h-4 text-blue-500/50" aria-hidden="true" />
                            <span>14-day free trial</span>
                        </div>
                        <div className="flex items-center gap-3">
                            <CheckCircle2 className="w-4 h-4 text-blue-500/50" aria-hidden="true" />
                            <span>No credit card required</span>
                        </div>
                        <div className="flex items-center gap-3">
                            <CheckCircle2 className="w-4 h-4 text-blue-500/50" aria-hidden="true" />
                            <span>Cancel anytime</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default CTASection;
