import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { BarChart3, Bot, Zap, Shield, LayoutDashboard } from 'lucide-react';

const FeatureCard = ({ icon: Icon, title, description, className, index }) => {
    const prefersReducedMotion = useReducedMotion();

    return (
        <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : index * 0.1, ease: 'easeOut' }}
            viewport={{ once: true, margin: "-50px" }}
            className={`p-8 monochrome-card group ${className}`}
        >
            <div className="w-10 h-10 bg-blue-500/5 flex items-center justify-center mb-6 transition-transform duration-300 group-hover:-translate-y-1 rounded-lg border border-blue-500/20">
                <Icon className="w-5 h-5 text-blue-500" aria-hidden="true" />
            </div>
            {/* Benefit-first Title */}
            <h3 className="text-xl font-bold text-white mb-3 tracking-tight">{title}</h3>
            {/* Context/Proof Description */}
            <p className="text-neutral-400 leading-relaxed text-balance">{description}</p>
        </motion.div>
    );
};

const FeatureBento = () => {
    return (
        <section id="features" className="py-32 relative border-t border-white/[0.03]">
            <div className="container mx-auto px-6">
                <div className="text-center max-w-3xl mx-auto mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 tracking-tight text-balance">
                        Spend your time analyzing, not querying.
                    </h2>
                    <p className="text-lg text-neutral-400">
                        Built for speed and precision. Skip the complex setups and get straight to the insights.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-hidden">
                    {/* Large Card 1 */}
                    <FeatureCard
                        icon={Bot}
                        title="Cut reporting time from 4 hours to 15 minutes"
                        description="Chat with your data in plain English. Just ask 'What dropped our conversion rate on Tuesday?'—DataSage handles the joins, queries, and charting automatically."
                        className="md:col-span-2 md:row-span-2 bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={0}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={LayoutDashboard}
                        title="One-click Executive Dashboards"
                        description="Upload your raw exports. Get a perfectly formatted dashboard in seconds without configuring widgets."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={1}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={BarChart3}
                        title="Say goodbye to chart fishing"
                        description="Stop guessing which visualization works. The engine recommends the exact right chart for the data shape."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={2}
                    />

                    {/* Wide Card */}
                    <FeatureCard
                        icon={Zap}
                        title="Analyze 5M+ rows in the browser"
                        description="Our specialized web-assembly engine runs locally in your browser. No server roundtrips, no loading spinners."
                        className="md:col-span-2 bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={3}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={Shield}
                        title="Your data stays yours"
                        description="Enterprise-grade architecture. Your queries are never used to train our models. Cancel anytime."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={4}
                    />
                </div>
            </div>
        </section>
    );
};

export default FeatureBento;
