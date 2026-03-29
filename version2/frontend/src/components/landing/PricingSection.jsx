import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

const PricingSection = () => {
    const [isAnnual, setIsAnnual] = useState(true);

    const checkIcon = <Check className="w-5 h-5 text-sky-400 shrink-0" />;

    return (
        <section id="pricing" className="py-32 relative bg-[#0A0A0A] border-y border-white/[0.03]">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-20">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white"
                    >
                        Simple, transparent pricing.
                    </motion.h2>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="flex items-center justify-center gap-6 mt-10"
                    >
                        <span className={`text-sm font-semibold transition-colors ${!isAnnual ? 'text-white' : 'text-neutral-500'}`}>Monthly</span>
                        <button
                            onClick={() => setIsAnnual(!isAnnual)}
                            className="w-16 h-8 rounded-full bg-white/[0.05] border border-white/[0.1] relative flex items-center transition-all hover:border-white/20 px-1"
                            aria-label="Toggle pricing period"
                        >
                            <motion.div
                                layout
                                className="w-6 h-6 bg-blue-500 rounded-full shadow-[0_0_15px_rgba(59,130,246,0.5)]"
                                animate={{ x: isAnnual ? 32 : 0 }}
                                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                            />
                        </button>
                        <span className={`text-sm font-semibold transition-colors ${isAnnual ? 'text-white' : 'text-neutral-500'}`}>
                            Annually <span className="text-blue-400 bg-blue-400/10 px-3 py-1 rounded-full text-[10px] uppercase font-bold ml-2 border border-blue-400/20 tracking-wider">Save 20%</span>
                        </span>
                    </motion.div>
                </div>

                <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto items-stretch">
                    {/* Starter */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="bg-[#0D0D0F] border border-white/[0.05] p-10 rounded-[2rem] flex flex-col"
                    >
                        <h3 className="text-xl font-bold mb-2 text-white">Starter</h3>
                        <p className="text-neutral-500 text-sm mb-10 leading-relaxed">Perfect for individuals and side-projects.</p>
                        <div className="text-4xl font-bold mb-10 text-white">
                            ${isAnnual ? '0' : '0'}
                            <span className="text-base font-normal text-neutral-500 tracking-normal ml-2">/mo</span>
                        </div>
                        <button className="w-full bg-white/[0.03] hover:bg-white/[0.08] text-white border border-white/[0.05] py-4 rounded-2xl font-semibold mb-10 transition-all">Get Started</button>
                        <ul className="space-y-5 text-sm text-neutral-400 mt-auto">
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Up to 10k rows / file</span></li>
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>3 dashboard conversions</span></li>
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Community support</span></li>
                        </ul>
                    </motion.div>

                    {/* Pro */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="bg-blue-500 p-[1px] rounded-[2rem] relative shadow-[0_0_50px_rgba(59,130,246,0.15)] transform md:scale-105"
                    >
                        <div className="bg-[#0D0D0F] h-full rounded-[2rem] p-10 flex flex-col relative overflow-hidden">
                            <div className="absolute top-6 right-8 bg-blue-500 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                                Recommended
                            </div>
                            <h3 className="text-xl font-bold mb-2 text-white">Pro</h3>
                            <p className="text-neutral-500 text-sm mb-10 leading-relaxed">For professionals who need serious power.</p>
                            <div className="text-4xl font-bold mb-10 text-white flex items-baseline gap-2">
                                ${isAnnual ? '29' : '39'}
                                <span className="text-base font-normal text-neutral-500 tracking-normal">/mo</span>
                            </div>
                            <button className="w-full bg-blue-500 hover:bg-blue-600 text-white py-4 rounded-2xl font-bold mb-10 shadow-[0_0_20px_rgba(59,130,246,0.3)] transition-all">Start Free Trial</button>
                            <ul className="space-y-5 text-sm text-neutral-300 mt-auto">
                                <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Everything in Starter</span></li>
                                <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Up to 5M rows / file</span></li>
                                <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Unlimited conversions</span></li>
                                <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Analytics Insights Engine</span></li>
                                <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Priority status</span></li>
                            </ul>
                        </div>
                    </motion.div>

                    {/* Enterprise */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.3 }}
                        className="bg-[#0D0D0F] border border-white/[0.05] p-10 rounded-[2rem] flex flex-col"
                    >
                        <h3 className="text-xl font-bold mb-2 text-white">Enterprise</h3>
                        <p className="text-neutral-500 text-sm mb-10 leading-relaxed">Custom infrastructure and security.</p>
                        <div className="text-4xl font-bold mb-10 text-white">Custom</div>
                        <button className="w-full bg-white/[0.03] hover:bg-white/[0.08] text-white border border-white/[0.05] py-4 rounded-2xl font-semibold mb-10 transition-all">Contact Sales</button>
                        <ul className="space-y-5 text-sm text-neutral-400 mt-auto">
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Everything in Pro</span></li>
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Direct Connectors</span></li>
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>SSO & RBAC security</span></li>
                            <li className="flex items-start gap-4"><Check className="w-4 h-4 text-blue-500 mt-0.5" /> <span>Success Manager</span></li>
                        </ul>
                    </motion.div>
                </div>
            </div>
        </section>
    );
};

export default PricingSection;
