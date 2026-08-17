import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Database, MessageSquareText, BrainCircuit } from 'lucide-react';

const ACCENT = '#F97316';

const Step = ({ icon, number, title, description, delay }) => {
    const Icon = icon;
    const prefersReducedMotion = useReducedMotion();

    return (
        <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : delay, ease: 'easeOut' }}
            viewport={{ once: true, margin: "-50px" }}
            className="flex flex-col items-center text-center p-8 bg-[#0D0D0F] border border-white/[0.03] rounded-3xl relative z-10"
        >
            <div className="w-12 h-12 flex items-center justify-center mb-6 relative rounded-xl border"
                style={{ background: 'rgba(249,115,22,0.1)', border: '1px solid rgba(249,115,22,0.25)', color: ACCENT }}>
                <Icon className="w-6 h-6" aria-hidden="true" />
                <div className="absolute -top-3 -right-3 w-6 h-6 text-white flex items-center justify-center text-[10px] font-bold rounded-full shadow-lg"
                    style={{ background: ACCENT }}>
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
                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5" style={{ color: ACCENT }}>How it works</div>
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 tracking-tight text-balance">
                        From raw data to shared understanding.
                    </h2>
                    <p className="text-lg text-neutral-400 max-w-2xl mx-auto text-balance">
                        Three steps. No setup week. No re-explaining your business to a chatbot.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-12 max-w-6xl mx-auto relative">
                    {/* Connecting line */}
                    <div className="hidden md:block absolute top-14 left-[16%] right-[16%] h-px bg-white/[0.05]" aria-hidden="true">
                        <motion.div
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: 1 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 1.5, ease: "easeInOut" }}
                            className="h-full origin-left"
                            style={{ background: ACCENT }}
                        />
                    </div>

                    <Step
                        icon={Database}
                        number="1"
                        title="Connect data"
                        description="Upload a CSV or Excel file, import a Google Sheet, or connect Postgres, MySQL, MongoDB, Supabase, and more."
                        delay={0}
                    />
                    <Step
                        icon={MessageSquareText}
                        number="2"
                        title="Ask in plain English"
                        description="'What dropped conversion on Tuesday?' Signal writes the SQL, runs it on DuckDB, and charts the answer — showing its work."
                        delay={0.1}
                    />
                    <Step
                        icon={BrainCircuit}
                        number="3"
                        title="Teach it once"
                        description="Correct anything. The belief store learns your metric definitions and terminology — so accuracy compounds with every conversation."
                        delay={0.2}
                    />
                </div>
            </div>
        </section>
    );
};

export default HowItWorks;
