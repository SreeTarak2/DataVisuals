import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2 } from 'lucide-react';

const UseCases = () => {
    const [activeTab, setActiveTab] = useState('analysts');

    const tabs = [
        { id: 'analysts', label: 'Data Analysts' },
        { id: 'business', label: 'Business Users' },
        { id: 'students', label: 'Students & Researchers' },
    ];

    const content = {
        analysts: {
            title: "Automate the Boring Stuff",
            description: "Stop spending hours cleaning data and building the same charts. Let AI handle the grunt work so you can focus on advanced modeling and strategy.",
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
                "Understand statistical concepts with AI explanations",
                "Generate citation-ready visualizations",
                "No complex software installation required"
            ]
        }
    };

    return (
        <section className="py-24 bg-slate-950">
            <div className="container mx-auto px-4">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">Built for <span className="text-blue-400">Everyone</span></h2>
                    <p className="text-lg text-slate-400">Whether you're a pro or just starting out, we've got you covered.</p>
                </div>

                <div className="max-w-4xl mx-auto">
                    {/* Tabs */}
                    <div className="flex flex-wrap justify-center gap-4 mb-12">
                        {tabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`px-6 py-3 rounded-full text-sm font-semibold transition-all duration-300 ${activeTab === tab.id
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30 scale-105'
                                        : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white border border-slate-800'
                                    }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Content Area */}
                    <div className="relative min-h-[300px]">
                        <AnimatePresence mode='wait'>
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3 }}
                                className="bg-slate-900/50 border border-slate-800 rounded-3xl p-8 md:p-12 relative overflow-hidden"
                            >
                                {/* Decorative background blob */}
                                <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>

                                <div className="grid md:grid-cols-2 gap-12 items-center relative z-10">
                                    <div>
                                        <h3 className="text-3xl font-bold text-white mb-4">{content[activeTab].title}</h3>
                                        <p className="text-slate-400 mb-8 text-lg">{content[activeTab].description}</p>
                                        <ul className="space-y-4">
                                            {content[activeTab].features.map((feature, idx) => (
                                                <li key={idx} className="flex items-start text-slate-300">
                                                    <CheckCircle2 className="w-5 h-5 text-green-400 mr-3 mt-1 flex-shrink-0" />
                                                    <span>{feature}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                    {/* Visual Placeholder for Persona */}
                                    <div className="hidden md:flex items-center justify-center p-8 bg-slate-950/50 rounded-2xl border border-slate-800/50">
                                        <div className="text-center">
                                            <div className="w-20 h-20 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse">
                                                <span className="text-4xl">
                                                    {activeTab === 'analysts' ? '📊' : activeTab === 'business' ? '💼' : '🎓'}
                                                </span>
                                            </div>
                                            <p className="text-slate-500 font-mono text-sm">Mode: {activeTab.toUpperCase()}</p>
                                        </div>
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
