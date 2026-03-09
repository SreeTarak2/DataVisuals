import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { UploadCloud, BrainCircuit, LineChart } from 'lucide-react';

const Step = ({ icon: Icon, number, title, description, delay }) => {
    const prefersReducedMotion = useReducedMotion();

    return (
        <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : delay, ease: 'easeOut' }}
            viewport={{ once: true, margin: "-50px" }}
            className="flex flex-col items-center text-center p-8 monochrome-card relative z-10"
        >
            <div className="w-12 h-12 bg-slate-50 text-slate-950 flex items-center justify-center mb-6 relative">
                <Icon className="w-6 h-6" aria-hidden="true" />
                <div className="absolute -top-3 -right-3 w-6 h-6 bg-sky-400 text-slate-950 flex items-center justify-center text-xs font-bold tabular-data">
                    {number}
                </div>
            </div>
            <h3 className="text-xl font-bold text-slate-50 mb-3 tracking-tight">{title}</h3>
            <p className="text-slate-400 text-balance leading-relaxed">{description}</p>
        </motion.div>
    );
};

const HowItWorks = () => {
    return (
        <section id="how-it-works" className="py-32 bg-[#020617] border-b border-slate-900">
            <div className="container mx-auto px-6">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-slate-50 mb-6 tracking-tight text-balance">
                        From raw data to insights in seconds.
                    </h2>
                    <p className="text-lg text-slate-400 max-w-2xl mx-auto text-balance">
                        No coding. No complex setup. Just drop your file and let the engine do the work.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto relative">
                    {/* Connecting Line (Desktop) */}
                    <div className="hidden md:block absolute top-14 left-[16%] right-[16%] h-px bg-slate-800" aria-hidden="true">
                        <motion.div
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: 1 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 1.5, ease: "easeInOut" }}
                            className="h-full bg-sky-500 origin-left"
                        />
                    </div>

                    <Step
                        icon={UploadCloud}
                        number="1"
                        title="Upload Data"
                        description="Drag and drop your CSV or Excel files. The engine automatically detects schemas and cleans the data."
                        delay={0}
                    />
                    <Step
                        icon={BrainCircuit}
                        number="2"
                        title="AI Engines Run"
                        description="The system analyzes patterns, identifies anomalies, and infers statistical significance instantly."
                        delay={0.1}
                    />
                    <Step
                        icon={LineChart}
                        number="3"
                        title="View Dashboard"
                        description="Get a fully interactive executive dashboard, ready to share or export immediately."
                        delay={0.2}
                    />
                </div>
            </div>
        </section>
    );
};

export default HowItWorks;
