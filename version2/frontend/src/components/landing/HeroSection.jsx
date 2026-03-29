'use client';
import React from 'react';
import { motion } from 'framer-motion';
import {
    ArrowRight,
    Database,
    Layout,
    Activity,
    Settings,
    BarChart3,
    Binary,
    Mail,
    ChevronRight,
    Search,
    Bell,
    User,
    TrendingUp,
    Users,
    CreditCard,
    Target
} from 'lucide-react';
import { Link } from 'react-router-dom';

const HeroSection = () => {
    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1,
                ease: 'easeOut',
                duration: 0.4
            }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 30 },
        visible: {
            opacity: 1,
            y: 0,
            transition: {
                duration: 0.8,
                ease: [0.16, 1, 0.3, 1]
            }
        }
    };

    return (
        <section className="relative min-h-screen flex flex-col items-center pt-32 pb-20 overflow-hidden bg-[#0A0A0A]">
            {/* Elegant Background Shadows */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute -top-[10%] left-[5%] w-[40vw] h-[40vw] bg-blue-500/5 rounded-full blur-[120px]" />
                <div className="absolute top-[20%] -right-[5%] w-[35vw] h-[35vw] bg-indigo-500/5 rounded-full blur-[100px]" />

                {/* Minimalist Grid Pattern */}
                <div className="absolute inset-0 opacity-[0.02]"
                    style={{ backgroundImage: 'linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)', backgroundSize: '60px 60px' }}
                />
            </div>

            <div className="container mx-auto px-4 z-10 relative flex flex-col items-center text-center">
                <motion.div
                    className="max-w-6xl mx-auto flex flex-col items-center"
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                >
                    {/* Professional Subtle Badge - Mirror Inspiration */}
                    <motion.div variants={itemVariants} className="mb-10">
                        <Link to="/contact" className="inline-flex items-center gap-3 px-3 py-1.5 rounded-full bg-neutral-900 border border-neutral-800 hover:border-neutral-700 transition-all duration-300 group shadow-lg">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500/50 opacity-100"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                            </span>
                            <span className="text-[11px] font-medium text-neutral-300 tracking-tight group-hover:text-white transition-colors">
                                Meet DataSage — AI for your data stack
                            </span>
                            <ChevronRight className="w-3.5 h-3.5 text-neutral-500 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                        </Link>
                    </motion.div>

                    {/* Massive Bold Headline - High Lead Precision */}
                    <motion.h1
                        variants={itemVariants}
                        className="text-6xl sm:text-7xl lg:text-[100px] font-bold tracking-tight text-white mb-10 leading-[0.9] text-balance"
                    >
                        Turn raw data into executive <span className="text-white/60">dashboards.</span>
                    </motion.h1>

                    {/* Sophisticated Subheadline */}
                    <motion.p
                        variants={itemVariants}
                        className="text-lg md:text-2xl text-neutral-400 max-w-3xl mb-14 font-medium leading-[1.4] text-balance opacity-80"
                    >
                        Stop writing SQL for basic questions. Upload your CSV or connect your database, and let the engine instantly generate professional, interactive charts.
                    </motion.p>

                    {/* High-Contrast CTAs - Fixed to Inspiration Style */}
                    <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center gap-5 mb-28 w-fit">
                        <Link to="/register" className="w-full sm:w-auto">
                            <button className="px-10 py-4.5 bg-white text-black font-bold rounded-full text-lg hover:bg-neutral-200 active:scale-[0.98] transition-all flex items-center gap-3 shadow-[0_0_40px_rgba(255,255,255,0.15)] w-full">
                                Get started <ArrowRight className="w-5 h-5" />
                            </button>
                        </Link>
                        <Link to="/demo" className="w-full sm:w-auto">
                            <button className="px-10 py-4.5 border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-900 text-white font-bold rounded-full text-lg backdrop-blur-md active:scale-[0.98] transition-all flex items-center gap-3 w-full">
                                <Mail className="w-5 h-5 opacity-60" /> Book a Demo
                            </button>
                        </Link>
                    </motion.div>

                    {/* Refined Dashboard Visual - Mirroring Inspiration Grid */}
                    <motion.div
                        variants={itemVariants}
                        className="w-full relative px-4 perspective-[2000px]"
                    >
                        <motion.div
                            initial={{ rotateX: 12, rotateY: -10, y: 100, opacity: 0 }}
                            animate={{ rotateX: 6, rotateY: -6, y: 0, opacity: 1 }}
                            transition={{ duration: 1.5, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
                            className="relative transform-gpu shadow-[0_80px_160px_rgba(0,0,0,0.9),0_0_100px_rgba(59,130,246,0.05)] rounded-2xl overflow-hidden border border-white/5 bg-[#0D0D0F] max-w-6xl mx-auto"
                        >
                            <div className="flex flex-col h-[500px] md:h-[750px]">
                                {/* Window Chrome / Top Bar */}
                                <div className="h-14 bg-[#141417] flex items-center justify-between px-6 border-b border-white/[0.03]">
                                    <div className="flex items-center gap-4">
                                        <div className="flex gap-2">
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5"></div>
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5"></div>
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5"></div>
                                        </div>
                                        <div className="h-6 w-px bg-white/5 mx-2" />
                                        <div className="flex items-center gap-2 text-[11px] font-medium text-neutral-400">
                                            <Database className="w-3.5 h-3.5" />
                                            <span>datasets / production_metrics</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-black/40 rounded-md border border-white/5">
                                            <Search className="w-3 h-3 text-neutral-500" />
                                            <span className="text-[10px] text-neutral-500 font-mono">cmd + k</span>
                                        </div>
                                        <Bell className="w-4 h-4 text-neutral-500" />
                                        <div className="w-6 h-6 rounded-full bg-neutral-800 border border-white/5 flex items-center justify-center">
                                            <User className="w-3 h-3 text-neutral-400" />
                                        </div>
                                    </div>
                                </div>

                                <div className="flex-1 flex overflow-hidden">
                                    {/* Sidebar Mockup - Inspiration Style */}
                                    <div className="w-20 md:w-56 bg-[#111113] border-r border-white/5 hidden md:flex flex-col py-6 px-4 gap-1 text-left">
                                        <p className="text-[10px] uppercase font-bold text-neutral-600 tracking-wider mb-4 px-2">Main Menu</p>
                                        <div className="flex items-center gap-3 px-3 py-2 bg-blue-500/10 text-blue-500 rounded-lg">
                                            <Layout className="w-4 h-4" />
                                            <span className="text-xs font-semibold">Dashboard</span>
                                        </div>
                                        {['Analytics', 'Documents', 'Reports', 'Team', 'Settings'].map((item, i) => (
                                            <div key={i} className="flex items-center gap-3 px-3 py-2 text-neutral-500 hover:text-neutral-300 transition-colors cursor-pointer rounded-lg hover:bg-white/5">
                                                {i === 0 && <Activity className="w-4 h-4" />}
                                                {i === 1 && <BarChart3 className="w-4 h-4" />}
                                                {i === 2 && <TrendingUp className="w-4 h-4" />}
                                                {i === 3 && <Users className="w-4 h-4" />}
                                                {i === 4 && <Settings className="w-4 h-4" />}
                                                <span className="text-xs font-medium">{item}</span>
                                            </div>
                                        ))}

                                        <div className="mt-auto p-4 bg-gradient-to-br from-blue-600/10 to-transparent border border-blue-500/20 rounded-xl">
                                            <p className="text-[10px] font-bold text-blue-400 mb-1">Upgrade Pro</p>
                                            <p className="text-[9px] text-neutral-500 leading-tight">Get advanced AI narratives and unlimited datasets.</p>
                                        </div>
                                    </div>

                                    {/* Main Content Area - Inspiration Card Grid */}
                                    <div className="flex-1 p-6 md:p-10 flex flex-col gap-8 bg-[#0D0D0F] overflow-y-auto custom-scrollbar">
                                        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
                                            <div className="text-left">
                                                <h3 className="text-2xl font-bold text-white mb-1 tracking-tight">Executive Overview</h3>
                                                <p className="text-xs text-neutral-500 uppercase tracking-widest font-semibold flex items-center gap-2 text-left">
                                                    Updated 2 minutes ago <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                                                </p>
                                            </div>
                                            <div className="flex gap-4">
                                                <button className="px-4 py-2 bg-white text-black text-[11px] font-bold rounded-lg hover:bg-neutral-200 transition-colors">Export PDF</button>
                                                <button className="px-4 py-2 bg-neutral-900 text-white text-[11px] font-bold rounded-lg border border-white/5 hover:bg-neutral-800 transition-colors">Share Report</button>
                                            </div>
                                        </div>

                                        {/* KPI Cards Grid - Directly from Inspiration */}
                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                                            {[
                                                { label: 'Total Revenue', value: '$12,450.00', trend: '+12.5%', icon: CreditCard },
                                                { label: 'New Customers', value: '1,234', trend: '+18.2%', icon: Users },
                                                { label: 'Active Projects', value: '45,678', trend: '-2.4%', icon: Target },
                                                { label: 'Growth Rate', value: '4.5%', trend: '+0.8%', icon: TrendingUp }
                                            ].map((card, i) => (
                                                <div key={i} className="p-5 rounded-2xl bg-white/[0.01] border border-white/5 flex flex-col gap-3 group hover:bg-white/[0.03] transition-all cursor-default text-left">
                                                    <div className="flex justify-between items-start">
                                                        <div className="p-2 bg-neutral-900 rounded-lg border border-white/5 group-hover:border-blue-500/30 transition-colors">
                                                            <card.icon className="w-4 h-4 text-neutral-400 group-hover:text-blue-500 transition-colors" />
                                                        </div>
                                                        <span className={`text-[10px] font-bold ${card.trend.startsWith('+') ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                            {card.trend}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <p className="text-2xl font-bold text-white tracking-tight">{card.value}</p>
                                                        <p className="text-[10px] text-neutral-600 uppercase font-bold tracking-wider">{card.label}</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>

                                        {/* Main Chart Section */}
                                        <div className="p-8 rounded-2xl bg-white/[0.01] border border-white/5 flex flex-col gap-8 flex-1 min-h-[300px] relative text-left">
                                            <div className="flex justify-between items-baseline">
                                                <div className="text-left">
                                                    <p className="text-xs text-neutral-500 uppercase font-bold tracking-widest mb-1">Transaction History</p>
                                                    <p className="text-3xl font-bold text-white tracking-tighter">$142,500.00 <span className="text-sm font-medium text-emerald-500 ml-2">↑ 24%</span></p>
                                                </div>
                                                <div className="flex gap-2">
                                                    {['7D', '30D', '90D', 'All'].map(t => (
                                                        <button key={t} className={`px-3 py-1.5 text-[10px] font-bold rounded-md border ${t === '30D' ? 'bg-blue-600 border-blue-600 text-white' : 'bg-neutral-900 border-white/5 text-neutral-500 hover:text-neutral-300'}`}>
                                                            {t}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>

                                            <div className="flex-1 flex items-end gap-3 px-2 pb-4">
                                                {[30, 45, 60, 35, 75, 40, 85, 30, 95, 45, 65, 80, 50, 70, 40, 90, 60, 85, 40, 65, 50, 95, 30, 70].map((h, i) => (
                                                    <motion.div
                                                        key={i}
                                                        initial={{ height: 0 }}
                                                        animate={{ height: `${h}%` }}
                                                        transition={{ duration: 1.2, delay: 1 + (i * 0.02), ease: "easeOut" }}
                                                        className={`flex-1 rounded-t-sm transition-all duration-300 ${i === 19 ? 'bg-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.5)]' : 'bg-neutral-800'}`}
                                                    />
                                                ))}
                                            </div>

                                            {/* Floating AI Narrative Box */}
                                            <motion.div
                                                initial={{ opacity: 0, x: 20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: 2.5 }}
                                                className="absolute top-1/2 right-8 -translate-y-1/2 w-64 glass-panel p-5 rounded-2xl border border-blue-500/20 bg-blue-500/5 shadow-2xl z-20 text-left"
                                            >
                                                <div className="flex items-center gap-2 mb-3">
                                                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                                                    <p className="text-[10px] text-blue-400 uppercase font-bold tracking-widest">AI Observation</p>
                                                </div>
                                                <p className="text-xs text-neutral-300 leading-relaxed font-medium">
                                                    "Revenue spike detected in North America. Correlating with recent campaign 'DataSage-v2' deployment."
                                                </p>
                                            </motion.div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Elegant Reflected Shadow */}
                        <div className="absolute -bottom-20 inset-x-0 h-60 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/40 to-transparent z-20 pointer-events-none"></div>
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
};

export default HeroSection;
