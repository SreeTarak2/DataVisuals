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
        <section id="use-cases" className="py-32 bg-[#0A0A0A] border-b border-white/[0.03]">
            <div className="container mx-auto px-6">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 tracking-tight text-balance">
                        Built for everyone.
                    </h2>
                    <p className="text-lg text-neutral-400">
                        Purpose-built tools for every skill level in the data chain.
                    </p>
                </div>

                <div className="max-w-5xl mx-auto">
                    {/* Tabs */}
                    <div className="flex flex-col md:flex-row justify-center gap-4 mb-12">
                        {tabs.map((tab) => {
                            const Icon = tab.icon;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`px-8 py-4 flex items-center justify-center gap-3 text-sm font-semibold transition-all duration-300 rounded-2xl border ${activeTab === tab.id
                                        ? 'bg-blue-500 text-white border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.2)]'
                                        : 'bg-white/[0.03] text-neutral-400 hover:text-white border-white/[0.05] hover:border-white/10'
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
                    <div className="min-h-[450px] bg-[#0D0D0F] border border-white/[0.05] rounded-[2rem] overflow-hidden p-1 shadow-2xl">
                        <AnimatePresence mode='wait'>
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.3 }}
                                className="p-8 md:p-16 h-full"
                                role="tabpanel"
                            >
                                <div className="grid md:grid-cols-2 gap-16 items-center">
                                    <div className="text-left">
                                        <h3 className="text-3xl font-bold text-white mb-4 tracking-tight">{content[activeTab].title}</h3>
                                        <p className="text-neutral-400 mb-10 text-lg leading-relaxed">{content[activeTab].description}</p>
                                        <ul className="space-y-4">
                                            {content[activeTab].features.map((feature, idx) => (
                                                <li key={idx} className="flex items-start text-neutral-300">
                                                    <CheckCircle2 className="w-5 h-5 text-blue-500 mr-4 flex-shrink-0" aria-hidden="true" />
                                                    <span>{feature}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                    <div className="hidden md:flex flex-col items-center justify-center p-12 bg-white/[0.02] border border-white/[0.05] rounded-3xl h-full">
                                        <div className="w-20 h-20 bg-blue-500/10 border border-blue-500/20 rounded-2xl flex items-center justify-center mb-6">
                                            {activeTab === 'analysts' && <LayoutDashboard className="w-10 h-10 text-blue-500" />}
                                            {activeTab === 'business' && <Brain className="w-10 h-10 text-blue-500" />}
                                            {activeTab === 'students' && <GraduationCap className="w-10 h-10 text-blue-500" />}
                                        </div>
                                        <p className="text-neutral-500 font-mono text-xs tracking-widest uppercase">
                                            {activeTab} module
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
