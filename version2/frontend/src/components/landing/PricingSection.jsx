import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

const PricingSection = () => {
    const [isAnnual, setIsAnnual] = useState(true);

    const checkIcon = <Check className="w-5 h-5 text-sky-400 shrink-0" />;

    return (
        <section id="pricing" className="py-32 relative bg-slate-950/50">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-slate-50"
                    >
                        Simple, Transparent Pricing
                    </motion.h2>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="flex items-center justify-center gap-4 mt-8"
                    >
                        <span className={`text-sm font-medium transition-colors ${!isAnnual ? 'text-white' : 'text-slate-400'}`}>Monthly</span>
                        <button
                            onClick={() => setIsAnnual(!isAnnual)}
                            className="w-14 h-7 rounded-full bg-slate-800 border border-slate-700 relative flex items-center transition-colors focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none"
                            aria-label="Toggle pricing period"
                        >
                            <motion.div
                                layout
                                className="w-5 h-5 bg-sky-400 rounded-full absolute shadow-md shadow-sky-400/20"
                                animate={{ left: isAnnual ? 'calc(100% - 1.5rem)' : '0.25rem' }}
                                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                            />
                        </button>
                        <span className={`text-sm font-medium transition-colors ${isAnnual ? 'text-white' : 'text-slate-400'}`}>
                            Annually <span className="text-sky-400 bg-sky-400/10 px-2 py-0.5 rounded-full text-xs ml-1 border border-sky-400/20">Save 20%</span>
                        </span>
                    </motion.div>
                </div>

                <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto items-center">
                    {/* Starter */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="monochrome-card p-8 rounded-2xl md:h-[95%]"
                    >
                        <h3 className="text-xl font-semibold mb-2 text-slate-50">Starter</h3>
                        <p className="text-slate-400 text-sm mb-6 h-10">Perfect for individuals and side-projects.</p>
                        <div className="text-4xl font-bold mb-8 text-slate-50">
                            ${isAnnual ? '0' : '0'}
                            <span className="text-base font-normal text-slate-400 tracking-normal">/mo</span>
                        </div>
                        <button className="w-full btn-secondary py-3 rounded-lg font-medium mb-8">Get Started</button>
                        <ul className="space-y-4 text-sm text-slate-300">
                            <li className="flex items-start gap-3">{checkIcon} <span>Up to 10k rows / file</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>3 dashboard conversions</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Community support</span></li>
                        </ul>
                    </motion.div>

                    {/* Pro */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="monochrome-card p-8 rounded-2xl border-sky-400/50 relative shadow-2xl shadow-sky-900/20 bg-slate-900/80 md:h-[105%] flex flex-col justify-center transform md:-translate-y-4"
                    >
                        <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-sky-500 text-slate-950 text-xs font-bold px-4 py-1.5 rounded-full uppercase tracking-wider">
                            Recommended
                        </div>
                        <h3 className="text-xl font-semibold mb-2 text-slate-50">Pro</h3>
                        <p className="text-slate-400 text-sm mb-6 h-10">For professionals who need serious analytical power.</p>
                        <div className="text-4xl font-bold mb-8 text-slate-50 flex items-end">
                            ${isAnnual ? '29' : '39'}
                            <span className="text-base font-normal text-slate-400 tracking-normal mb-1">/mo</span>
                        </div>
                        <button className="w-full btn-primary py-3 rounded-lg font-semibold mb-8 shadow-lg shadow-sky-500/20 hover:shadow-sky-500/40">Start Free Trial</button>
                        <ul className="space-y-4 text-sm text-slate-300">
                            <li className="flex items-start gap-3">{checkIcon} <span>Everything in Starter</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Up to 5M rows / file</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Unlimited dashboard conversions</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Advanced QUIS Insights Engine</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Priority email support</span></li>
                        </ul>
                    </motion.div>

                    {/* Enterprise */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.3 }}
                        className="monochrome-card p-8 rounded-2xl md:h-[95%]"
                    >
                        <h3 className="text-xl font-semibold mb-2 text-slate-50">Enterprise</h3>
                        <p className="text-slate-400 text-sm mb-6 h-10">Custom infrastructure and security for large teams.</p>
                        <div className="text-4xl font-bold mb-8 text-slate-50">Custom</div>
                        <button className="w-full btn-secondary py-3 rounded-lg font-medium mb-8">Contact Sales</button>
                        <ul className="space-y-4 text-sm text-slate-300">
                            <li className="flex items-start gap-3">{checkIcon} <span>Everything in Pro</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Direct Database Connectors (Postgres, Snowflake)</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>SSO & Role-based access</span></li>
                            <li className="flex items-start gap-3">{checkIcon} <span>Dedicated Success Manager</span></li>
                        </ul>
                    </motion.div>
                </div>
            </div>
        </section>
    );
};

export default PricingSection;
