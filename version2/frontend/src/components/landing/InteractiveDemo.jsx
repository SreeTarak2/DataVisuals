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
        <section id="demo" className="py-24 relative overflow-hidden bg-[#0A0A0A]">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white"
                    >
                        Interactive Product Demo
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-lg md:text-xl text-neutral-400 max-w-2xl mx-auto"
                    >
                        Experience the power of AI-driven analytics firsthand. Click around to see how DataSage instantly visualizes data.
                    </motion.p>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.7, delay: 0.2 }}
                    className="relative rounded-[2rem] border border-white/[0.05] bg-[#0D0D0F] shadow-2xl overflow-hidden flex flex-col md:flex-row min-h-[600px]"
                >
                    {/* Sidebar / Tabs */}
                    <div className="w-full md:w-64 bg-white/[0.02] border-b md:border-b-0 md:border-r border-white/[0.05] p-6 flex md:flex-col gap-3 overflow-x-auto">
                        {tabs.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-3 px-5 py-4 rounded-xl text-sm font-medium transition-all duration-300 whitespace-nowrap ${isActive ? 'bg-blue-500 text-white shadow-lg' : 'text-neutral-500 hover:bg-white/[0.03] hover:text-neutral-200'}`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>

                    {/* Dashboard Content Area */}
                    <div className="flex-1 p-8 relative">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                                className="h-full flex flex-col gap-8"
                            >
                                {/* KPI Cards Row */}
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                                    {[1, 2, 3].map((i) => (
                                        <div key={i} className="bg-white/[0.03] border border-white/[0.03] rounded-2xl p-6">
                                            <div className="text-neutral-500 text-xs font-mono tracking-widest uppercase mb-2">Metric 0{i}</div>
                                            <div className="text-3xl font-bold text-white mb-2">
                                                {activeTab === 'sales' ? `$${(Math.random() * 100).toFixed(1)}k` : (Math.random() * 1000).toFixed(0)}
                                            </div>
                                            <div className="text-xs text-blue-400 flex items-center gap-1 font-semibold">
                                                <TrendingUp className="w-3 h-3" /> +{(Math.random() * 15).toFixed(1)}% this week
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Main Chart Area */}
                                <div className="flex-1 bg-white/[0.02] border border-white/[0.03] rounded-[1.5rem] p-8 flex flex-col justify-end relative overflow-hidden min-h-[300px]">
                                    <div className="absolute top-6 left-8 text-neutral-300 font-medium">Trend Analysis</div>

                                    {/* Mock Bar Chart */}
                                    {activeTab === 'sales' && (
                                        <div className="flex items-end justify-between h-48 gap-3 w-full mt-8">
                                            {[...Array(12)].map((_, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ height: 0 }}
                                                    animate={{ height: `${Math.random() * 80 + 20}%` }}
                                                    transition={{ duration: 0.5, delay: i * 0.05 }}
                                                    className="w-full bg-blue-500/80 rounded-t-md hover:bg-blue-400 cursor-pointer transition-colors"
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
                                                    fill="url(#gradient-demo)"
                                                    stroke="none"
                                                />
                                                <motion.path
                                                    initial={{ pathLength: 0 }}
                                                    animate={{ pathLength: 1 }}
                                                    transition={{ duration: 1.5, ease: "easeInOut" }}
                                                    d="M0,80 Q10,70 20,60 T40,40 T60,50 T80,20 T100,10"
                                                    fill="none"
                                                    stroke="#3b82f6"
                                                    strokeWidth="2"
                                                />
                                                <defs>
                                                    <linearGradient id="gradient-demo" x1="0" x2="0" y1="0" y2="1">
                                                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
                                                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                                                    </linearGradient>
                                                </defs>
                                            </svg>
                                        </div>
                                    )}

                                    {/* Mock Mixed Chart */}
                                    {activeTab === 'performance' && (
                                        <div className="flex items-end justify-between h-48 gap-3 w-full mt-8 relative text-left">
                                            {[...Array(10)].map((_, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ height: 0 }}
                                                    animate={{ height: `${Math.random() * 70 + 10}%` }}
                                                    transition={{ duration: 0.5, delay: i * 0.05 }}
                                                    className="w-full bg-blue-600/40 rounded-t-md hover:bg-blue-500/60 transition-colors"
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
