import React from 'react';
import { motion } from 'framer-motion';
import { UploadCloud, BrainCircuit, LineChart } from 'lucide-react';

const Step = ({ icon: Icon, number, title, description, delay }) => (
    <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay }}
        viewport={{ once: true }}
        className="relative flex flex-col items-center text-center p-6 z-10"
    >
        <div className="w-16 h-16 rounded-full bg-slate-900 border border-blue-500/30 flex items-center justify-center mb-6 shadow-[0_0_30px_-5px_theme(colors.blue.500/0.3)]">
            <Icon className="w-8 h-8 text-blue-400" />
            <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-sm border-4 border-slate-950">
                {number}
            </div>
        </div>
        <h3 className="text-xl font-bold text-white mb-3">{title}</h3>
        <p className="text-slate-400">{description}</p>
    </motion.div>
);

const HowItWorks = () => {
    return (
        <section className="py-24 bg-slate-950 relative overflow-hidden">
            {/* Background Gradients */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[300px] bg-blue-600/10 blur-[100px] rounded-full pointer-events-none"></div>

            <div className="container mx-auto px-4">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">From Data to Insight in <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">Seconds</span></h2>
                    <p className="text-lg text-slate-400 max-w-2xl mx-auto">No coding. No complex setup. Just drag, drop, and discover.</p>
                </div>

                <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
                    {/* Connecting Line (Desktop) */}
                    <div className="hidden md:block absolute top-14 left-[16%] right-[16%] h-0.5 bg-gradient-to-r from-blue-900 via-blue-500 to-blue-900 opacity-30"></div>

                    <Step
                        icon={UploadCloud}
                        number="1"
                        title="Upload Data"
                        description="Drag and drop your CSV or Excel files. We automatically detect types and clean your data."
                        delay={0}
                    />
                    <Step
                        icon={BrainCircuit}
                        number="2"
                        title="AI Analysis"
                        description="Our multi-agent system analyzes patterns, correlations, and anomalies instantly."
                        delay={0.2}
                    />
                    <Step
                        icon={LineChart}
                        number="3"
                        title="Visual Insights"
                        description="Get an interactive dashboard and ask questions in plain English to dive deeper."
                        delay={0.4}
                    />
                </div>
            </div>
        </section>
    );
};

export default HowItWorks;
