import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { CheckCircle2, LayoutDashboard, Brain, GraduationCap } from 'lucide-react';

const UseCases = () => {
    const [activeTab, setActiveTab] = useState('analysts');
    const prefersReducedMotion = useReducedMotion();

    const tabs = [
        { id: 'analysts', label: 'Data Analysts', icon: LayoutDashboard },
        { id: 'business', label: 'Business Users', icon: Brain },
        { id: 'students', label: 'Students', icon: GraduationCap },
    ];

    const content = {
        analysts: {
            title: "Automate the Boring Stuff",
            description: "Stop spending hours cleaning data and building boilerplate charts. Let the engine handle the grunt work so you can focus on advanced modeling.",
            features: [
                "Automated data cleaning & type inference",
                "Instant EDA (Exploratory Data Analysis)",
                "Export clean data & charts to Python/R",
                "Semantic search across all your datasets"
            ]
        },
        business: {
            title: "Answers without SQL",
            description: "You shouldn't need a data science degree to understand your business performance. Just ask questions in plain English.",
            features: [
                "Natural language Q&A interface",
                "Executive dashboards generated in seconds",
                "Identify trends and anomalies automatically",
                "Secure, private data processing"
            ]
        },
        students: {
            title: "Learn Faster with AI",
            description: "Upload your research data or class assignments and get instant visualizations and statistical summaries.",
            features: [
                "Free to use for academic purposes",
                "Understand statistical concepts with context",
                "Generate citation-ready visualizations",
                "No complex software installation required"
            ]
        }
    };

    return (
        <section id="use-cases" className="py-32 bg-[#020617] border-b border-slate-900">
            <div className="container mx-auto px-6">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-slate-50 mb-6 tracking-tight text-balance">
                        Built for everyone.
                    </h2>
                    <p className="text-lg text-slate-400">
                        Purpose-built tools for every skill level in the data chain.
                    </p>
                </div>

                <div className="max-w-5xl mx-auto">
                    {/* Tabs */}
                    <div className="flex flex-col md:flex-row justify-center gap-2 mb-12">
                        {tabs.map((tab) => {
                            const Icon = tab.icon;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`px-6 py-4 flex items-center justify-center gap-3 text-sm font-semibold transition-all duration-200 focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:outline-none border ${activeTab === tab.id
                                        ? 'bg-slate-50 text-slate-950 border-slate-50'
                                        : 'bg-transparent text-slate-400 hover:text-slate-50 border-slate-800 hover:border-slate-600'
                                        }`}
                                    aria-selected={activeTab === tab.id}
                                    role="tab"
                                >
                                    <Icon className="w-4 h-4" aria-hidden="true" />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>

                    {/* Content Area */}
                    <div className="min-h-[400px] monochrome-card p-1">
                        <AnimatePresence mode='wait'>
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -10 }}
                                transition={{ duration: 0.2, ease: 'easeOut' }}
                                className="bg-[#020617] p-8 md:p-16 h-full"
                                role="tabpanel"
                            >
                                <div className="grid md:grid-cols-2 gap-16 items-center">
                                    <div>
                                        <h3 className="text-3xl font-bold text-slate-50 mb-4 tracking-tight">{content[activeTab].title}</h3>
                                        <p className="text-slate-400 mb-10 text-lg leading-relaxed">{content[activeTab].description}</p>
                                        <ul className="space-y-4">
                                            {content[activeTab].features.map((feature, idx) => (
                                                <li key={idx} className="flex items-start text-slate-300">
                                                    <CheckCircle2 className="w-5 h-5 text-slate-500 mr-4 flex-shrink-0" aria-hidden="true" />
                                                    <span>{feature}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                    <div className="hidden md:flex flex-col items-center justify-center p-12 bg-slate-900/50 border border-slate-800 h-full">
                                        <div className="w-16 h-16 bg-slate-800 border border-slate-700 flex items-center justify-center mb-6">
                                            {activeTab === 'analysts' && <LayoutDashboard className="w-8 h-8 text-sky-400" />}
                                            {activeTab === 'business' && <Brain className="w-8 h-8 text-sky-400" />}
                                            {activeTab === 'students' && <GraduationCap className="w-8 h-8 text-sky-400" />}
                                        </div>
                                        <p className="text-slate-500 font-mono text-sm tracking-widest uppercase">
                                            {activeTab}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default UseCases;
