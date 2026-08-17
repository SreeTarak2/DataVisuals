import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart3, LineChart, PieChart, TrendingUp, Users, DollarSign } from 'lucide-react';

const ACCENT = '#F97316';

const tabs = [
    { id: 'sales', label: 'Sales Metrics', icon: DollarSign },
    { id: 'users', label: 'User Growth', icon: Users },
    { id: 'performance', label: 'Sys Performance', icon: TrendingUp },
];

// Deterministic sample data (illustrative, not live)
const DATA = {
    sales: {
        kpis: [
            { label: 'Monthly Recurring Revenue', value: '$84,200', delta: '+6.8%' },
            { label: 'Net Revenue', value: '$112,450', delta: '+12.5%' },
            { label: 'Avg Order Value', value: '$248.10', delta: '+3.2%' },
        ],
        chart: [32, 45, 38, 52, 60, 55, 68, 74, 70, 82, 88, 96],
        label: 'Net revenue, last 12 months',
    },
    users: {
        kpis: [
            { label: 'Active Users', value: '48,210', delta: '+18.2%' },
            { label: 'New Signups', value: '3,405', delta: '+9.4%' },
            { label: 'Activation Rate', value: '61%', delta: '+2.1%' },
        ],
        chart: [12, 18, 22, 20, 28, 35, 33, 41, 47, 52, 58, 66],
        label: 'Active users, last 12 months',
    },
    performance: {
        kpis: [
            { label: 'Query Latency (p95)', value: '142ms', delta: '-18%' },
            { label: 'Uptime', value: '99.98%', delta: '+0.01%' },
            { label: 'Requests / day', value: '1.2M', delta: '+22%' },
        ],
        chart: [85, 78, 82, 70, 74, 66, 60, 58, 55, 50, 48, 44],
        label: 'Query latency (ms), trending down',
    },
};

const InteractiveDemo = () => {
    const [activeTab, setActiveTab] = useState(tabs[0].id);
    const data = DATA[activeTab];

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
                        A preview of the product.
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-lg md:text-xl text-neutral-400 max-w-2xl mx-auto"
                    >
                        Sample dashboards styled like what Signal generates. Connect your own data to see it live.
                    </motion.p>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.7, delay: 0.2 }}
                    className="relative rounded-[2rem] border border-white/[0.05] bg-[#0D0D0F] shadow-2xl overflow-hidden flex flex-col md:flex-row min-h-[560px]"
                >
                    {/* Tabs */}
                    <div role="tablist" aria-label="Sample dashboards" className="w-full md:w-64 bg-white/[0.02] border-b md:border-b-0 md:border-r border-white/[0.05] p-6 flex md:flex-col gap-3 overflow-x-auto">
                        {tabs.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    role="tab"
                                    aria-selected={isActive}
                                    aria-controls={`panel-${tab.id}`}
                                    id={`tab-${tab.id}`}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-3 px-5 py-4 rounded-xl text-sm font-medium transition-all duration-300 whitespace-nowrap ${isActive ? 'text-white shadow-lg' : 'text-neutral-500 hover:bg-white/[0.03] hover:text-neutral-200'}`}
                                    style={isActive ? { background: ACCENT, boxShadow: '0 8px 24px -8px rgba(249,115,22,0.5)' } : undefined}
                                >
                                    <Icon className="w-4 h-4" />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>

                    {/* Content */}
                    <div className="flex-1 p-8 relative">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeTab}
                                role="tabpanel"
                                id={`panel-${activeTab}`}
                                aria-labelledby={`tab-${activeTab}`}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                                className="h-full flex flex-col gap-8"
                            >
                                {/* KPI row */}
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                                    {data.kpis.map((kpi, i) => (
                                        <div key={i} className="bg-white/[0.03] border border-white/[0.03] rounded-2xl p-6">
                                            <div className="text-neutral-500 text-xs font-mono tracking-widest uppercase mb-2">{kpi.label}</div>
                                            <div className="text-3xl font-bold text-white mb-2">{kpi.value}</div>
                                            <div className="text-xs font-semibold flex items-center gap-1" style={{ color: ACCENT }}>
                                                <TrendingUp className="w-3 h-3" /> {kpi.delta} this period
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Chart */}
                                <div className="flex-1 bg-white/[0.02] border border-white/[0.03] rounded-[1.5rem] p-8 flex flex-col justify-end relative overflow-hidden min-h-[280px]">
                                    <div className="absolute top-6 left-8 text-neutral-300 font-medium">{data.label}</div>
                                    <div className="flex items-end justify-between h-48 gap-3 w-full mt-8">
                                        {data.chart.map((h, i) => (
                                            <motion.div
                                                key={i}
                                                initial={{ height: 0 }}
                                                animate={{ height: `${h}%` }}
                                                transition={{ duration: 0.5, delay: i * 0.05 }}
                                                className="w-full rounded-t-md transition-colors"
                                                style={{ background: i === data.chart.length - 1 ? ACCENT : 'rgba(249,115,22,0.55)' }}
                                            />
                                        ))}
                                    </div>
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
