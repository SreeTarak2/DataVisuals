import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, BrainCircuit, Activity } from 'lucide-react';

const AdvancedCapabilities = () => {
    return (
        <section id="capabilities" className="py-32 relative bg-[#0A0A0A] overflow-hidden">
            {/* Background elements */}
            <div className="absolute right-0 top-0 w-1/2 h-1/2 bg-blue-500/5 blur-[150px] -z-10 rounded-full" />
            <div className="absolute left-0 bottom-0 w-1/2 h-1/2 bg-blue-600/5 blur-[150px] -z-10 rounded-full" />

            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-24 max-w-3xl mx-auto">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white"
                    >
                        Intelligence that scales with your ambition
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-lg md:text-xl text-neutral-400"
                    >
                        Go beyond standard bar charts. DataSage's AI engines analyze the shape of your data to uncover insights you didn't know you should look for.
                    </motion.p>
                </div>

                {/* Feature 1 */}
                <div className="grid md:grid-cols-2 gap-12 lg:gap-24 items-center mb-32 text-left">
                    <motion.div
                        initial={{ opacity: 0, x: -40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                        className="order-2 md:order-1"
                    >
                        <div className="w-12 h-12 bg-blue-500/10 border border-blue-500/20 rounded-xl flex items-center justify-center mb-6">
                            <Sparkles className="w-6 h-6 text-blue-400" />
                        </div>
                        <h3 className="text-2xl md:text-3xl font-bold mb-4 text-white tracking-tight">Automated AI Insights</h3>
                        <p className="text-neutral-400 text-lg leading-relaxed mb-6">
                            Our proprietary Insight Engine (QUIS) scans your dataset for anomalies, correlations, and segment behaviors. It synthesizes findings into a readable executive summary before you even ask your first question.
                        </p>
                        <ul className="space-y-3">
                            {['Anomaly detection', 'Cohort behavior analysis', 'Trend forecasting'].map((item, i) => (
                                <li key={i} className="flex items-center gap-3 text-neutral-300 pointer-events-none">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, x: 40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                        className="order-1 md:order-2 aspect-[4/3] rounded-2xl border border-white/[0.05] bg-[#0D0D0F] flex items-center justify-center relative shadow-2xl overflow-hidden"
                    >
                        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-blue-500/10 to-transparent"></div>
                        <div className="space-y-4 w-3/4">
                            <div className="h-4 w-1/3 bg-white/5 rounded animate-pulse" />
                            <div className="h-4 w-full bg-white/5 rounded animate-pulse" />
                            <div className="h-4 w-2/3 bg-white/5 rounded animate-pulse" />
                            <div className="h-24 w-full bg-blue-500/10 border border-blue-500/20 rounded-lg mt-6" />
                        </div>
                    </motion.div>
                </div>

                {/* Feature 2 (Reversed) */}
                <div className="grid md:grid-cols-2 gap-12 lg:gap-24 items-center text-left">
                    <motion.div
                        initial={{ opacity: 0, x: -40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                        className="aspect-[4/3] rounded-2xl border border-white/[0.05] bg-[#0D0D0F] flex items-center justify-center relative shadow-2xl overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 to-transparent"></div>
                        <div className="w-3/4 h-3/4 flex gap-4 items-end justify-center">
                            {[40, 70, 45, 90, 60, 100].map((h, i) => (
                                <div key={i} className="w-8 bg-blue-500/40 rounded-t-md relative flex-shrink-0" style={{ height: `${h}%` }}>
                                    {i === 3 && (
                                        <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-white text-black text-[10px] font-bold py-1 px-2 rounded">
                                            Peak
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, x: 40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                    >
                        <div className="w-12 h-12 bg-blue-500/10 border border-blue-500/20 rounded-xl flex items-center justify-center mb-6">
                            <BrainCircuit className="w-6 h-6 text-blue-400" />
                        </div>
                        <h3 className="text-2xl md:text-3xl font-bold mb-4 text-white tracking-tight">Smart Chart Selection</h3>
                        <p className="text-neutral-400 text-lg leading-relaxed mb-6">
                            Never stare at a "select chart type" dropdown again. DataSage evaluates your dataset's schema and relationships to instantly recommend the perfect visualization format—whether it's a funnel, sunburst, or scatter plot.
                        </p>
                        <button className="text-white hover:text-blue-400 font-medium border-b border-blue-400/30 pb-0.5 transition-colors">
                            Explore visualization types &rarr;
                        </button>
                    </motion.div>
                </div>
            </div>
        </section>
    );
};

export default AdvancedCapabilities;
