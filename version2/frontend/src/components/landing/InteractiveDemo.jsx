import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart3, LineChart, PieChart, TrendingUp, Users, DollarSign } from 'lucide-react';

const tabs = [
    { id: 'sales', label: 'Sales Metrics', icon: DollarSign },
    { id: 'users', label: 'User Growth', icon: Users },
    { id: 'performance', label: 'Sys Performance', icon: TrendingUp },
];

const InteractiveDemo = () => {
    const [activeTab, setActiveTab] = useState(tabs[0].id);

    return (
        <section id="demo" className="py-24 relative overflow-hidden bg-slate-950">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        Interactive Product Demo
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto"
                    >
                        Experience the power of AI-driven analytics firsthand. Click around to see how DataSage instantly visualizes data.
                    </motion.p>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.7, delay: 0.2 }}
                    className="relative rounded-2xl border border-white/10 bg-[#020617] shadow-2xl overflow-hidden flex flex-col md:flex-row min-h-[500px]"
                >
                    {/* Sidebar / Tabs */}
                    <div className="w-full md:w-64 bg-slate-900/50 border-b md:border-b-0 md:border-r border-white/5 p-4 flex md:flex-col gap-2 overflow-x-auto">
                        {tabs.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${isActive ? 'bg-sky-500/10 text-sky-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>

                    {/* Dashboard Content Area */}
                    <div className="flex-1 p-6 relative bg-gradient-to-br from-slate-900/20 to-transparent">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                                className="h-full flex flex-col gap-6"
                            >
                                {/* KPI Cards Row */}
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                    {[1, 2, 3].map((i) => (
                                        <div key={i} className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                                            <div className="text-slate-400 text-sm mb-1">Metric {i}</div>
                                            <div className="text-2xl font-bold text-slate-100 mb-2">
                                                {activeTab === 'sales' ? `$${(Math.random() * 100).toFixed(1)}k` : (Math.random() * 1000).toFixed(0)}
                                            </div>
                                            <div className="text-xs text-emerald-400 flex items-center gap-1">
                                                <TrendingUp className="w-3 h-3" /> +{(Math.random() * 15).toFixed(1)}% this week
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Main Chart Area */}
                                <div className="flex-1 bg-slate-800/30 border border-white/5 rounded-xl p-6 flex flex-col justify-end relative overflow-hidden min-h-[250px]">
                                    <div className="absolute top-4 left-4 text-slate-300 font-medium">Trend Analysis</div>

                                    {/* Mock Bar Chart */}
                                    {activeTab === 'sales' && (
                                        <div className="flex items-end justify-between h-48 gap-2 w-full mt-8">
                                            {[...Array(12)].map((_, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ height: 0 }}
                                                    animate={{ height: `${Math.random() * 80 + 20}%` }}
                                                    transition={{ duration: 0.5, delay: i * 0.05 }}
                                                    className="w-full bg-sky-500/80 rounded-t-sm hover:bg-sky-400 cursor-pointer"
                                                />
                                            ))}
                                        </div>
                                    )}

                                    {/* Mock Line Chart (Simplified with SVG) */}
                                    {activeTab === 'users' && (
                                        <div className="h-48 w-full mt-8 relative flex items-end">
                                            <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 100 100">
                                                <motion.path
                                                    initial={{ pathLength: 0 }}
                                                    animate={{ pathLength: 1 }}
                                                    transition={{ duration: 1.5, ease: "easeInOut" }}
                                                    d="M0,80 Q10,70 20,60 T40,40 T60,50 T80,20 T100,10 L100,100 L0,100 Z"
                                                    fill="url(#gradient)"
                                                    stroke="none"
                                                />
                                                <motion.path
                                                    initial={{ pathLength: 0 }}
                                                    animate={{ pathLength: 1 }}
                                                    transition={{ duration: 1.5, ease: "easeInOut" }}
                                                    d="M0,80 Q10,70 20,60 T40,40 T60,50 T80,20 T100,10"
                                                    fill="none"
                                                    stroke="#0ea5e9"
                                                    strokeWidth="2"
                                                />
                                                <defs>
                                                    <linearGradient id="gradient" x1="0" x2="0" y1="0" y2="1">
                                                        <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.4" />
                                                        <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
                                                    </linearGradient>
                                                </defs>
                                            </svg>
                                        </div>
                                    )}

                                    {/* Mock Mixed Chart */}
                                    {activeTab === 'performance' && (
                                        <div className="flex items-end justify-between h-48 gap-2 w-full mt-8 relative">
                                            {[...Array(8)].map((_, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ height: 0 }}
                                                    animate={{ height: `${Math.random() * 60 + 10}%` }}
                                                    transition={{ duration: 0.5, delay: i * 0.05 }}
                                                    className="w-full bg-purple-500/50 rounded-t-sm"
                                                />
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    </div>
                </motion.div>
            </div>
        </section>
    );
};

export default InteractiveDemo;
