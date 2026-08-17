import React from 'react';
import { motion } from 'framer-motion';
import {
    ArrowRight,
    Database,
    Layout,
    Activity,
    Settings,
    BarChart3,
    TrendingUp,
    Users,
    CreditCard,
    Target,
    Sparkles,
    CheckCircle2
} from 'lucide-react';
import { Link } from 'react-router-dom';

const ACCENT = '#F97316';
const ACCENT_SOFT = 'rgba(249, 115, 22, 0.1)';
const ACCENT_BORDER = 'rgba(249, 115, 22, 0.25)';

const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.1, ease: 'easeOut', duration: 0.4 }
    }
};

const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] }
    }
};

const HeroSection = () => {
    return (
        <section className="relative min-h-screen flex flex-col items-center pt-32 pb-20 overflow-hidden bg-[#0A0A0A]">
            {/* Background: warm radial glows + precision grid */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute -top-[10%] left-[5%] w-[40vw] h-[40vw] bg-[rgba(249,115,22,0.07)] rounded-full blur-[120px]" />
                <div className="absolute top-[20%] -right-[5%] w-[35vw] h-[35vw] bg-[rgba(249,115,22,0.05)] rounded-full blur-[100px]" />
                <div className="absolute inset-0 opacity-[0.03]"
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
                    {/* Announcement badge */}
                    <motion.div variants={itemVariants} className="mb-10">
                        <Link to="/demo" className="inline-flex items-center gap-3 px-3 py-1.5 rounded-full bg-neutral-900 border border-neutral-800 hover:border-[rgba(249,115,22,0.4)] transition-all duration-300 group">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: ACCENT }} />
                                <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: ACCENT }} />
                            </span>
                            <span className="text-[11px] font-medium text-neutral-300 tracking-tight group-hover:text-white transition-colors">
                                Meet Signal — AI analytics that remembers your business
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-neutral-500 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                        </Link>
                    </motion.div>

                    {/* Headline */}
                    <motion.h1
                        variants={itemVariants}
                        className="text-6xl sm:text-7xl lg:text-[96px] font-bold tracking-tight text-white mb-10 leading-[0.95] text-balance"
                    >
                        Turn raw data into{' '}
                        <span className="hero-gradient">answers that remember.</span>
                    </motion.h1>

                    {/* Subheadline */}
                    <motion.p
                        variants={itemVariants}
                        className="text-lg md:text-2xl text-neutral-400 max-w-3xl mb-14 font-medium leading-[1.4] text-balance opacity-90"
                    >
                        Upload a CSV or connect your database. Ask in plain English — Signal writes the SQL, builds the
                        charts, and learns your definitions so every answer gets more accurate.
                    </motion.p>

                    {/* CTAs */}
                    <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center gap-5 mb-10 w-fit">
                        <Link to="/register" className="w-full sm:w-auto">
                            <button className="px-10 py-4.5 bg-[#F97316] text-white font-bold rounded-full text-lg hover:bg-[#EA580C] active:scale-[0.98] transition-all flex items-center gap-3 shadow-[0_0_40px_rgba(249,115,22,0.35)] w-full">
                                Start free <ArrowRight className="w-5 h-5" />
                            </button>
                        </Link>
                        <Link to="/demo" className="w-full sm:w-auto">
                            <button className="px-10 py-4.5 border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-900 text-white font-bold rounded-full text-lg backdrop-blur-md active:scale-[0.98] transition-all flex items-center gap-3 w-full">
                                Book a demo
                            </button>
                        </Link>
                    </motion.div>

                    {/* Trust microcopy */}
                    <motion.p variants={itemVariants} className="text-xs text-neutral-500 mb-16">
                        Free to start · No credit card · Works with the data you already have
                    </motion.p>

                    {/* Dashboard visual */}
                    <motion.div
                        variants={itemVariants}
                        className="w-full relative px-4 perspective-[2000px]"
                    >
                        <motion.div
                            initial={{ rotateX: 12, rotateY: -10, y: 100, opacity: 0 }}
                            animate={{ rotateX: 6, rotateY: -6, y: 0, opacity: 1 }}
                            transition={{ duration: 1.5, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
                            className="relative transform-gpu shadow-[0_80px_160px_rgba(0,0,0,0.9),0_0_100px_rgba(249,115,22,0.06)] rounded-2xl overflow-hidden border border-white/5 bg-[#0D0D0F] max-w-6xl mx-auto"
                        >
                            <div className="flex flex-col h-[500px] md:h-[720px]">
                                {/* Window chrome */}
                                <div className="h-14 bg-[#141417] flex items-center justify-between px-6 border-b border-white/[0.03]">
                                    <div className="flex items-center gap-4">
                                        <div className="flex gap-2">
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5" />
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5" />
                                            <div className="w-3 h-3 rounded-full bg-neutral-800 border border-white/5" />
                                        </div>
                                        <div className="h-6 w-px bg-white/5 mx-2" />
                                        <div className="flex items-center gap-2 text-[11px] font-medium text-neutral-400">
                                            <Database className="w-3.5 h-3.5" />
                                            <span>datasets / production_metrics</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-black/40 rounded-md border border-white/5">
                                            <Sparkles className="w-3 h-3" style={{ color: ACCENT }} />
                                            <span className="text-[10px] text-neutral-500 font-mono">Ask anything…</span>
                                        </div>
                                        <div className="w-6 h-6 rounded-full bg-neutral-800 border border-white/5 flex items-center justify-center">
                                            <Users className="w-3 h-3 text-neutral-400" />
                                        </div>
                                    </div>
                                </div>

                                <div className="flex-1 flex overflow-hidden">
                                    {/* Sidebar */}
                                    <div className="w-20 md:w-56 bg-[#111113] border-r border-white/5 hidden md:flex flex-col py-6 px-4 gap-1 text-left">
                                        <p className="text-[10px] uppercase font-bold text-neutral-600 tracking-wider mb-4 px-2">Main Menu</p>
                                        <div className="flex items-center gap-3 px-3 py-2 rounded-lg" style={{ background: ACCENT_SOFT, color: ACCENT }}>
                                            <Layout className="w-4 h-4" />
                                            <span className="text-xs font-semibold">Dashboard</span>
                                        </div>
                                        {['Ask AI', 'Datasets', 'Connectors', 'Reports', 'Settings'].map((item, i) => (
                                            <div key={i} className="flex items-center gap-3 px-3 py-2 text-neutral-500 hover:text-neutral-300 transition-colors cursor-pointer rounded-lg hover:bg-white/5">
                                                {i === 0 && <Activity className="w-4 h-4" />}
                                                {i === 1 && <BarChart3 className="w-4 h-4" />}
                                                {i === 2 && <Database className="w-4 h-4" />}
                                                {i === 3 && <TrendingUp className="w-4 h-4" />}
                                                {i === 4 && <Settings className="w-4 h-4" />}
                                                <span className="text-xs font-medium">{item}</span>
                                            </div>
                                        ))}

                                        {/* Memory indicator */}
                                        <div className="mt-auto p-4 rounded-xl" style={{ background: ACCENT_SOFT, border: `1px solid ${ACCENT_BORDER}` }}>
                                            <p className="text-[10px] font-bold mb-1" style={{ color: ACCENT }}>Context memory active</p>
                                            <p className="text-[9px] text-neutral-500 leading-tight">12 corrections learned — answers stay consistent with your definitions.</p>
                                        </div>
                                    </div>

                                    {/* Main content */}
                                    <div className="flex-1 p-6 md:p-10 flex flex-col gap-8 bg-[#0D0D0F] overflow-y-auto custom-scrollbar">
                                        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
                                            <div className="text-left">
                                                <h3 className="text-2xl font-bold text-white mb-1 tracking-tight">Executive Overview</h3>
                                                <p className="text-xs text-neutral-500 uppercase tracking-widest font-semibold flex items-center gap-2 text-left">
                                                    Updated 2 minutes ago <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                                </p>
                                            </div>
                                            <div className="flex gap-4">
                                                <button className="px-4 py-2 text-[11px] font-bold rounded-lg border border-white/5 bg-neutral-900 hover:bg-neutral-800 transition-colors text-white">Export</button>
                                                <button className="px-4 py-2 text-[11px] font-bold rounded-lg text-white transition-colors" style={{ background: ACCENT }}>Ask AI</button>
                                            </div>
                                        </div>

                                        {/* KPI cards */}
                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                                            {[
                                                { label: 'Total Revenue', value: '$12,450.00', trend: '+12.5%', icon: CreditCard },
                                                { label: 'New Customers', value: '1,234', trend: '+18.2%', icon: Users },
                                                { label: 'Active Projects', value: '45,678', trend: '-2.4%', icon: Target },
                                                { label: 'Growth Rate', value: '4.5%', trend: '+0.8%', icon: TrendingUp }
                                            ].map((card, i) => (
                                                <div key={i} className="p-5 rounded-2xl bg-white/[0.01] border border-white/5 flex flex-col gap-3 group hover:bg-white/[0.03] transition-all cursor-default text-left">
                                                    <div className="flex justify-between items-start">
                                                        <div className="p-2 bg-neutral-900 rounded-lg border border-white/5 transition-colors" style={{ color: ACCENT }}>
                                                            <card.icon className="w-4 h-4" />
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

                                        {/* Chart + AI insight */}
                                        <div className="p-8 rounded-2xl bg-white/[0.01] border border-white/5 flex flex-col gap-8 flex-1 min-h-[300px] relative text-left">
                                            <div className="flex justify-between items-baseline">
                                                <div className="text-left">
                                                    <p className="text-xs text-neutral-500 uppercase font-bold tracking-widest mb-1">Transaction History</p>
                                                    <p className="text-3xl font-bold text-white tracking-tighter">$142,500.00 <span className="text-sm font-medium text-emerald-500 ml-2">↑ 24%</span></p>
                                                </div>
                                                <div className="flex gap-2">
                                                    {['7D', '30D', '90D', 'All'].map(t => (
                                                        <button key={t} className={`px-3 py-1.5 text-[10px] font-bold rounded-md border transition-colors ${t === '30D' ? 'text-white' : 'bg-neutral-900 border-white/5 text-neutral-500 hover:text-neutral-300'}`} style={t === '30D' ? { background: ACCENT, borderColor: ACCENT } : undefined}>
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
                                                        className={`flex-1 rounded-t-sm transition-all duration-300 ${i === 19 ? '' : 'bg-neutral-800'}`}
                                                        style={i === 19 ? { background: ACCENT, boxShadow: '0 0 20px rgba(249,115,22,0.5)' } : undefined}
                                                    />
                                                ))}
                                            </div>

                                            {/* Floating AI insight + correction chip */}
                                            <motion.div
                                                initial={{ opacity: 0, x: 20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: 2.5 }}
                                                className="absolute top-1/2 right-8 -translate-y-1/2 w-64 glass-panel p-5 rounded-2xl z-20 text-left shadow-2xl"
                                                style={{ border: `1px solid ${ACCENT_BORDER}`, background: 'rgba(249,115,22,0.06)' }}
                                            >
                                                <div className="flex items-center gap-2 mb-3">
                                                    <div className="w-2 h-2 rounded-full" style={{ background: ACCENT }} />
                                                    <p className="text-[10px] uppercase font-bold tracking-widest" style={{ color: ACCENT }}>AI Observation</p>
                                                </div>
                                                <p className="text-xs text-neutral-300 leading-relaxed font-medium">
                                                    "Revenue spike detected in North America. Correlating with recent campaign 'Signal-v2' deployment."
                                                </p>
                                                <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center gap-2">
                                                    <CheckCircle2 className="w-3 h-3" style={{ color: ACCENT }} />
                                                    <span className="text-[10px] text-neutral-400">Definition verified — uses your metric "Net Revenue"</span>
                                                </div>
                                            </motion.div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Reflected fade */}
                        <div className="absolute -bottom-20 inset-x-0 h-60 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/40 to-transparent z-20 pointer-events-none" />
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
};

export default HeroSection;
