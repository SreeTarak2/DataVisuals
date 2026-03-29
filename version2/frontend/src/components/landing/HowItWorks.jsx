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
            className="flex flex-col items-center text-center p-8 bg-[#0D0D0F] border border-white/[0.03] rounded-3xl relative z-10"
        >
            <div className="w-12 h-12 bg-blue-500/10 text-blue-500 flex items-center justify-center mb-6 relative rounded-xl border border-blue-500/20">
                <Icon className="w-6 h-6" aria-hidden="true" />
                <div className="absolute -top-3 -right-3 w-6 h-6 bg-blue-500 text-white flex items-center justify-center text-[10px] font-bold rounded-full shadow-lg">
                    {number}
                </div>
            </div>
            <h3 className="text-xl font-bold text-white mb-3 tracking-tight">{title}</h3>
            <p className="text-neutral-400 text-balance leading-relaxed">{description}</p>
        </motion.div>
    );
};

const HowItWorks = () => {
    return (
        <section id="how-it-works" className="py-32 bg-[#0A0A0A] border-y border-white/[0.03]">
            <div className="container mx-auto px-6">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 tracking-tight text-balance">
                        From raw data to insights in seconds.
                    </h2>
                    <p className="text-lg text-neutral-400 max-w-2xl mx-auto text-balance">
                        No coding. No complex setup. Just drop your file and let the engine do the work.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-12 max-w-6xl mx-auto relative">
                    {/* Connecting Line (Desktop) */}
                    <div className="hidden md:block absolute top-14 left-[16%] right-[16%] h-px bg-white/[0.05]" aria-hidden="true">
                        <motion.div
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: 1 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 1.5, ease: "easeInOut" }}
                            className="h-full bg-blue-500 origin-left"
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
