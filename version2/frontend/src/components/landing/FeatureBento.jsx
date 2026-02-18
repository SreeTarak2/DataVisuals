import React from 'react';
import { motion } from 'framer-motion';
import { BarChart3, Bot, Zap, Shield, Sparkles, LayoutDashboard } from 'lucide-react';

const FeatureCard = ({ icon: Icon, title, description, className, delay }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay }}
        viewport={{ once: true }}
        className={`p-6 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-blue-500/30 transition-all hover:bg-slate-800/50 group ${className}`}
    >
        <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4 group-hover:bg-blue-500/20 transition-colors">
            <Icon className="w-6 h-6 text-blue-400 group-hover:text-blue-300" />
        </div>
        <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
        <p className="text-slate-400 leading-relaxed">{description}</p>
    </motion.div>
);

const FeatureBento = () => {
    return (
        <section className="py-24 bg-slate-950">
            <div className="container mx-auto px-4">
                <div className="text-center max-w-3xl mx-auto mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">
                        Everything you need to <span className="text-blue-400">understand your data</span>.
                    </h2>
                    <p className="text-lg text-slate-400">
                        Replace your complex data stack with one simple, AI-powered platform.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
                    {/* Large Card 1 */}
                    <FeatureCard
                        icon={Bot}
                        title="AI Data Analyst"
                        description="Chat with your data in plain English. Ask questions, get answers, and uncover hidden insights instantly."
                        className="md:col-span-2 md:row-span-2 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-900/20"
                        delay={0}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={LayoutDashboard}
                        title="Auto-Dashboards"
                        description="Upload a file and get a professional dashboard generated in seconds."
                        delay={0.1}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={BarChart3}
                        title="Smart Charts"
                        description="AI recommends the best visualization for your specific dataset."
                        delay={0.2}
                    />

                    {/* Wide Card */}
                    <FeatureCard
                        icon={Zap}
                        title="Instant Processing"
                        description="Process millions of rows in the browser with our optimized engine."
                        className="md:col-span-2"
                        delay={0.3}
                    />

                    {/* Regular Card */}
                    <FeatureCard
                        icon={Shield}
                        title="Privacy First"
                        description="Your data is processed securely and never used to train our models."
                        delay={0.4}
                    />
                </div>
            </div>
        </section>
    );
};

export default FeatureBento;
