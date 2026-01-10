import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useTransform, useSpring, useMotionValue, useMotionTemplate } from 'framer-motion';
import {
  ArrowRight,
  BarChart3,
  Brain,
  Database,
  Zap,
  Shield,
  MessageSquare,
  Sparkles,
  Menu,
  X,
  CheckCircle2,
  TrendingUp,
  Globe,
  Layers
} from 'lucide-react';
import './landing.css';

// --- Components ---

const SpotlightCard = ({ children, className = "" }) => {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  function handleMouseMove({ currentTarget, clientX, clientY }) {
    const { left, top } = currentTarget.getBoundingClientRect();
    mouseX.set(clientX - left);
    mouseY.set(clientY - top);
  }

  return (
    <div
      className={`spotlight-card group relative border border-slate-800 bg-slate-900/50 overflow-hidden rounded-xl ${className}`}
      onMouseMove={handleMouseMove}
    >
      <motion.div
        className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition duration-300 group-hover:opacity-100"
        style={{
          background: useMotionTemplate`
            radial-gradient(
              650px circle at ${mouseX}px ${mouseY}px,
              rgba(59, 130, 246, 0.15),
              transparent 80%
            )
          `,
        }}
      />
      <div className="relative h-full">
        {children}
      </div>
    </div>
  );
};

const HeroDashboard = () => {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"]
  });

  const rotateX = useTransform(scrollYProgress, [0, 1], [20, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [1.05, 0.9]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <motion.div
      ref={ref}
      style={{
        rotateX: rotateX,
        scale: scale,
        opacity: opacity,
        transformPerspective: 1000
      }}
      className="relative mx-auto w-full max-w-5xl mt-16 perspective-1000"
    >
      <div className="hero-dashboard-glass rounded-xl overflow-hidden border border-slate-700/50 shadow-2xl aspect-[16/9] relative group">
        {/* Mockup Header */}
        <div className="h-10 border-b border-slate-700/50 bg-slate-900/50 flex items-center px-4 gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
            <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50" />
          </div>
          <div className="mx-auto w-64 h-5 rounded-md bg-slate-800/50 text-[10px] flex items-center justify-center text-slate-500 font-mono">
            datasage.ai/dashboard
          </div>
        </div>

        {/* Mockup Content */}
        <div className="p-6 grid grid-cols-12 gap-6 h-full bg-slate-950/80">
          {/* Sidebar */}
          <div className="col-span-2 hidden md:flex flex-col gap-4 border-r border-slate-800/50 pr-6">
            <div className="h-8 w-24 rounded bg-slate-800/50 animate-pulse" />
            <div className="space-y-2 mt-4">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="h-6 w-full rounded bg-slate-800/30" />
              ))}
            </div>
          </div>

          {/* Main Content */}
          <div className="col-span-12 md:col-span-10 flex flex-col gap-6">
            <div className="flex justify-between items-center">
              <div className="h-8 w-48 rounded bg-slate-800/50" />
              <div className="h-8 w-24 rounded bg-blue-500/20" />
            </div>

            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-24 rounded-lg bg-slate-900 border border-slate-800 p-4">
                  <div className="h-4 w-12 rounded bg-slate-800 mb-2" />
                  <div className="h-8 w-20 rounded bg-slate-700" />
                </div>
              ))}
            </div>

            <div className="flex-1 rounded-lg bg-slate-900 border border-slate-800 p-4 relative overflow-hidden">
              {/* Chart Mockup */}
              <div className="absolute bottom-0 left-0 right-0 h-32 flex items-end justify-between px-4 gap-2 opacity-50">
                {[40, 60, 45, 70, 50, 80, 65, 85, 75, 90, 60, 70].map((h, i) => (
                  <motion.div
                    key={i}
                    initial={{ height: 0 }}
                    animate={{ height: `${h}%` }}
                    transition={{ duration: 1, delay: i * 0.05 }}
                    className="w-full bg-gradient-to-t from-blue-500/50 to-cyan-400/50 rounded-t-sm"
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Reflection Overlay */}
        <div className="absolute inset-0 bg-gradient-to-tr from-white/5 to-transparent pointer-events-none" />
      </div>
    </motion.div>
  );
};

const Landing = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState(null);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-[#020617] text-white overflow-x-hidden selection:bg-blue-500/30">
      {/* Aurora Background */}
      <div className="aurora-container">
        <div className="aurora-blob aurora-blob-1" />
        <div className="aurora-blob aurora-blob-2" />
        <div className="aurora-blob aurora-blob-3" />
      </div>
      <div className="bg-noise" />

      {/* Navigation */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? 'glass-nav py-3' : 'py-5 bg-transparent'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2 group">
            <img
              src="/logo.png"
              alt="DataSage Logo"
              className="w-11 h-11 rounded-lg object-cover shadow-lg shadow-blue-500/20 group-hover:shadow-blue-500/40 transition-all"
            />
            <span className="text-lg font-bold tracking-tight text-white" style={{ fontFamily: "'Rajdhani', sans-serif" }}>Data<br></br>Sage</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            {['Features', 'How It Works', 'Testimonials'].map((item) => (
              <a key={item} href={`#${item.toLowerCase().replace(/\s+/g, '-')}`} className="text-sm font-medium text-slate-400 hover:text-white transition-colors">
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-4">
            <Link to="/login" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
              Sign In
            </Link>
            <Link to="/register" className="btn-premium px-4 py-2 rounded-lg text-sm font-semibold text-white">
              Get Started
            </Link>
          </div>

          <button className="md:hidden text-slate-300" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
            {isMobileMenuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </nav>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed inset-0 z-40 bg-slate-950 pt-24 px-6 md:hidden"
        >
          <div className="flex flex-col gap-6 text-lg">
            {['Features', 'How It Works', 'Testimonials'].map((item) => (
              <a key={item} href={`#${item.toLowerCase().replace(/\s+/g, '-')}`} onClick={() => setIsMobileMenuOpen(false)} className="text-slate-300">
                {item}
              </a>
            ))}
            <div className="h-px bg-slate-800 my-2" />
            <Link to="/login" className="text-slate-300">Sign In</Link>
            <Link to="/register" className="btn-premium py-3 rounded-lg text-center font-semibold">Get Started</Link>
          </div>
        </motion.div>
      )}

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-4 sm:px-6 overflow-hidden">
        <div className="max-w-7xl mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium mb-8"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            v2.0 is now live
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold tracking-tight text-white mb-6 max-w-4xl mx-auto leading-[1.1]"
          >
            Data analytics, <br />
            <span className="hero-title-gradient">reimagined for humans.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed"
          >
            Stop wrestling with SQL and spreadsheets. Just ask questions and get
            instant, visual answers powered by advanced AI.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-4 justify-center mb-20"
          >
            <Link to="/register" className="btn-premium h-12 px-8 rounded-lg flex items-center justify-center gap-2 font-semibold text-white">
              Start Analyzing Free
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to="/login" className="h-12 px-8 rounded-lg border border-slate-700 hover:bg-slate-800/50 flex items-center justify-center font-medium text-slate-300 transition-colors">
              View Demo
            </Link>
          </motion.div>

          {/* 3D Dashboard Mockup */}
          <HeroDashboard />
        </div>
      </section>

      {/* Social Proof Marquee */}
      <section className="py-10 border-y border-slate-800/50 bg-slate-950/50 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 mb-6 text-center">
          <p className="text-sm font-medium text-slate-500">TRUSTED BY INNOVATIVE TEAMS</p>
        </div>
        <div className="relative flex overflow-x-hidden marquee-container">
          <motion.div
            className="flex gap-16 items-center whitespace-nowrap py-2"
            animate={{ x: "-50%" }}
            transition={{ repeat: Infinity, ease: "linear", duration: 20 }}
          >
            {[...Array(2)].map((_, i) => (
              <React.Fragment key={i}>
                {['Acme Corp', 'GlobalTech', 'Nebula', 'Vertex', 'Horizon', 'Pinnacle', 'Zenith', 'Apex'].map((company) => (
                  <div key={company} className="text-xl font-bold text-slate-700 flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-slate-800" />
                    {company}
                  </div>
                ))}
              </React.Fragment>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Bento Grid */}
      <section id="features" className="py-24 px-4 sm:px-6 relative z-10">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
              Everything you need, <span className="text-blue-400">nothing you don't.</span>
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Powerful features wrapped in a beautiful, intuitive interface designed for speed.
            </p>
          </div>

          <div className="grid-bento">
            {/* Large Card 1 */}
            <SpotlightCard className="bento-span-2 bento-row-span-2 min-h-[400px]">
              <div className="p-8 h-full flex flex-col">
                <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-6">
                  <Brain className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-2xl font-bold text-white mb-4">AI-Powered Analyst</h3>
                <p className="text-slate-400 mb-8 max-w-md">
                  Ask complex questions in plain English. Our AI understands context, filters data, and generates the perfect visualization instantly.
                </p>
                <div className="mt-auto rounded-lg bg-slate-900 border border-slate-800 p-4 relative overflow-hidden">
                  <div className="flex gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400">AI</div>
                    <div className="text-sm text-slate-300 bg-slate-800/50 rounded-lg px-3 py-2 rounded-tl-none">
                      I found a 40% increase in user retention. Here's the breakdown by region.
                    </div>
                  </div>
                  <div className="h-32 bg-slate-800/30 rounded border border-slate-700/30 w-full" />
                </div>
              </div>
            </SpotlightCard>

            {/* Small Card 1 */}
            <SpotlightCard>
              <div className="p-6 h-full flex flex-col">
                <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center mb-4">
                  <BarChart3 className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Smart Charts</h3>
                <p className="text-sm text-slate-400">
                  Visualizations that adapt automatically to your data type and query context.
                </p>
              </div>
            </SpotlightCard>

            {/* Small Card 2 */}
            <SpotlightCard>
              <div className="p-6 h-full flex flex-col">
                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center mb-4">
                  <Zap className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Real-time</h3>
                <p className="text-sm text-slate-400">
                  Process millions of rows in seconds with our optimized columnar engine.
                </p>
              </div>
            </SpotlightCard>

            {/* Wide Card */}
            <SpotlightCard className="bento-span-2">
              <div className="p-8 flex flex-col md:flex-row items-center gap-8">
                <div className="flex-1">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center mb-4">
                    <Shield className="w-5 h-5 text-emerald-400" />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Enterprise Security</h3>
                  <p className="text-slate-400">
                    SOC2 compliant, end-to-end encryption, and role-based access control. Your data never leaves our secure enclave.
                  </p>
                </div>
                <div className="flex-1 w-full">
                  <div className="grid grid-cols-2 gap-3">
                    {['Encryption', 'SSO', 'Audit Logs', 'RBAC'].map(item => (
                      <div key={item} className="flex items-center gap-2 text-sm text-slate-300 bg-slate-950/50 p-3 rounded border border-slate-800">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </SpotlightCard>

            {/* Small Card 3 */}
            <SpotlightCard>
              <div className="p-6 h-full flex flex-col">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center mb-4">
                  <Globe className="w-5 h-5 text-orange-400" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Global Scale</h3>
                <p className="text-sm text-slate-400">
                  Deployed on edge networks worldwide for low-latency access anywhere.
                </p>
              </div>
            </SpotlightCard>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-24 px-4 sm:px-6 relative z-10 border-t border-slate-800/50 bg-slate-950/30">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
              From raw data to <span className="text-purple-400">insights in minutes.</span>
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              No complex setup. No data engineering degree required.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-12 relative">
            {/* Connecting Line */}
            <div className="hidden md:block absolute top-12 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-blue-500/20" />

            {[
              {
                step: '01',
                title: 'Connect Data',
                desc: 'Upload CSVs or connect your database (Postgres, MySQL, Snowflake) securely.',
                icon: Database,
                color: 'blue'
              },
              {
                step: '02',
                title: 'Ask Questions',
                desc: 'Type questions in plain English. "Show me revenue by region for last quarter."',
                icon: MessageSquare,
                color: 'purple'
              },
              {
                step: '03',
                title: 'Get Insights',
                desc: 'Receive instant, interactive visualizations and actionable summaries.',
                icon: Sparkles,
                color: 'cyan'
              }
            ].map((item, i) => (
              <div key={i} className="relative flex flex-col items-center text-center group">
                <div className={`w-24 h-24 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mb-6 relative z-10 group-hover:border-${item.color}-500/50 transition-colors duration-300 shadow-xl`}>
                  <div className={`absolute inset-0 bg-${item.color}-500/10 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
                  <item.icon className={`w-10 h-10 text-${item.color}-400`} />
                  <div className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-white">
                    {item.step}
                  </div>
                </div>
                <h3 className="text-xl font-bold text-white mb-3">{item.title}</h3>
                <p className="text-slate-400 leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className="py-24 px-4 sm:px-6 relative z-10">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
              Loved by <span className="text-cyan-400">data teams.</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                quote: "DataSage has completely transformed how we analyze our marketing data. It's like having a data scientist on call 24/7.",
                author: "Sarah Chen",
                role: "Head of Growth",
                company: "TechFlow"
              },
              {
                quote: "The speed at which we can go from raw data to insight is incredible. What used to take days now takes minutes.",
                author: "Michael Ross",
                role: "Product Manager",
                company: "Innovate"
              },
              {
                quote: "Finally, a tool that my entire team can use without needing to learn SQL. The natural language query is a game changer.",
                author: "Jessica Lee",
                role: "VP of Operations",
                company: "ScaleUp"
              }
            ].map((item, i) => (
              <div key={i} className="bg-slate-900/40 border border-slate-800 p-8 rounded-2xl backdrop-blur-sm hover:bg-slate-900/60 transition-colors">
                <div className="flex gap-1 mb-4">
                  {[1, 2, 3, 4, 5].map(star => (
                    <Sparkles key={star} className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                  ))}
                </div>
                <p className="text-slate-300 mb-6 leading-relaxed">"{item.quote}"</p>
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-sm font-bold text-white">
                    {item.author[0]}
                  </div>
                  <div>
                    <div className="font-semibold text-white">{item.author}</div>
                    <div className="text-xs text-slate-500">{item.role}, {item.company}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-4 sm:px-6 relative z-10 border-t border-slate-800/50 bg-slate-950/30">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight">
              Pricing plans
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Choose the right plan for your needs.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {/* Starter */}
            <div className="bg-slate-950 rounded-3xl p-2 flex flex-col border border-slate-800/50">
              <div className="bg-slate-900 rounded-[1.25rem] p-8">
                <div className="inline-block px-3 py-1 rounded-full bg-white text-slate-950 text-xs font-bold mb-6">
                  Starter
                </div>
                <div className="text-5xl font-bold text-white mb-2 tracking-tight">$0<span className="text-lg font-medium text-slate-400">/month</span></div>
                <p className="text-slate-400 font-medium">Perfect for individuals and hobbyists.</p>
              </div>

              <div className="p-8 pt-6 flex-1 flex flex-col">
                <Link to="/register" className="w-full py-4 rounded-full bg-white text-slate-950 font-bold hover:bg-slate-200 transition-colors text-center mb-8 shadow-lg shadow-white/5">
                  Get Started
                </Link>
                <ul className="space-y-4">
                  {['5 Datasets', 'Basic Charts', 'Community Support', '1 User'].map(feature => (
                    <li key={feature} className="flex items-center gap-3 text-sm font-medium text-slate-300">
                      <CheckCircle2 className="w-4 h-4 text-slate-500" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Professional */}
            <div className="bg-slate-950 rounded-3xl p-2 flex flex-col border border-blue-500/30 relative shadow-2xl shadow-blue-900/10">
              <div className="bg-gradient-to-br from-blue-900/40 to-blue-800/20 rounded-[1.25rem] p-8 border border-blue-500/20">
                <div className="inline-block px-3 py-1 rounded-full bg-blue-500 text-white text-xs font-bold mb-6 uppercase tracking-wide">
                  Most Popular
                </div>
                <div className="text-5xl font-bold text-white mb-2 tracking-tight">$29<span className="text-lg font-medium text-slate-400">/month</span></div>
                <p className="text-blue-200 font-medium">For growing teams and startups.</p>
              </div>

              <div className="p-8 pt-6 flex-1 flex flex-col">
                <Link to="/register" className="w-full py-4 rounded-full bg-white text-slate-950 font-bold hover:bg-slate-200 transition-colors text-center mb-8 shadow-lg shadow-blue-500/20">
                  Start Free Trial
                </Link>
                <ul className="space-y-4">
                  {['Unlimited Datasets', 'Advanced AI Analysis', 'Priority Support', '5 Users', 'Export to CSV/PDF'].map(feature => (
                    <li key={feature} className="flex items-center gap-3 text-sm font-medium text-white">
                      <CheckCircle2 className="w-4 h-4 text-blue-400" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Enterprise */}
            <div className="bg-slate-950 rounded-3xl p-2 flex flex-col border border-slate-800/50">
              <div className="bg-slate-900 rounded-[1.25rem] p-8">
                <div className="inline-block px-3 py-1 rounded-full bg-white text-slate-950 text-xs font-bold mb-6">
                  Enterprise
                </div>
                <div className="text-5xl font-bold text-white mb-2 tracking-tight">Custom</div>
                <p className="text-slate-400 font-medium">For large organizations with specific needs.</p>
              </div>

              <div className="p-8 pt-6 flex-1 flex flex-col">
                <Link to="/contact" className="w-full py-4 rounded-full bg-slate-800 text-white font-bold hover:bg-slate-700 transition-colors text-center mb-8 border border-slate-700">
                  Contact Sales
                </Link>
                <ul className="space-y-4">
                  {['Unlimited Users', 'SSO & SAML', 'Dedicated Success Manager', 'Custom Integrations', 'SLA'].map(feature => (
                    <li key={feature} className="flex items-center gap-3 text-sm font-medium text-slate-300">
                      <CheckCircle2 className="w-4 h-4 text-slate-500" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-24 px-4 sm:px-6 relative z-10">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-12 gap-12">
            {/* Left Column */}
            <div className="col-span-12 md:col-span-5 flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-300 text-xs font-medium mb-6">
                  <span className="relative flex h-2 w-2">
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                  </span>
                  Support
                </div>
                <h2 className="text-4xl md:text-5xl font-bold text-white mb-8 tracking-tight">
                  Frequently asked <br /> questions
                </h2>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 backdrop-blur-sm">
                <h3 className="text-xl font-bold text-white mb-2">Still have questions?</h3>
                <p className="text-slate-400 mb-6 text-sm">
                  Can't find the answer you're looking for? Please chat to our friendly team.
                </p>
                <Link to="/contact" className="w-full py-3 rounded-full bg-blue-600 hover:bg-blue-500 text-white font-bold transition-colors text-center shadow-lg shadow-blue-900/20 flex items-center justify-center">
                  Get in Touch
                </Link>
              </div>
            </div>

            {/* Right Column - Accordion */}
            <div className="col-span-12 md:col-span-7 space-y-4">
              {[
                {
                  q: "Is my data secure?",
                  a: "Yes, we use bank-grade encryption (AES-256) for all data at rest and in transit. We are SOC2 Type II compliant and conduct regular security audits."
                },
                {
                  q: "Can I connect my own database?",
                  a: "Absolutely. We support PostgreSQL, MySQL, Snowflake, BigQuery, and Redshift out of the box. You can also upload CSV/Excel files directly."
                },
                {
                  q: "Do I need to know SQL?",
                  a: "Not at all! DataSage is designed for non-technical users. You can ask questions in plain English like 'Show me revenue by region' and get instant charts."
                },
                {
                  q: "Can I export the charts?",
                  a: "Yes, you can export any visualization as PNG, SVG, or embed it directly into your own applications via iframe or React component."
                },
                {
                  q: "How does the free trial work?",
                  a: "You get full access to the Pro plan for 14 days. No credit card required. At the end of the trial, you can choose a plan or downgrade to the free tier."
                }
              ].map((item, i) => (
                <div
                  key={i}
                  className="bg-slate-900/30 border border-slate-800 rounded-xl overflow-hidden transition-all duration-300 hover:border-slate-700"
                >
                  <button
                    onClick={() => setActiveQuestion(activeQuestion === i ? null : i)}
                    className="w-full flex items-center justify-between p-6 text-left gap-4"
                  >
                    <span className="font-semibold text-white text-lg">{item.q}</span>
                    <div className={`w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center transition-transform duration-300 flex-shrink-0 ${activeQuestion === i ? 'rotate-180 bg-blue-500/20 text-blue-400' : 'text-slate-400'}`}>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  <motion.div
                    initial={false}
                    animate={{ height: activeQuestion === i ? 'auto' : 0, opacity: activeQuestion === i ? 1 : 0 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-hidden"
                  >
                    <div className="p-6 pt-0 text-slate-400 leading-relaxed border-t border-slate-800/50">
                      {item.a}
                    </div>
                  </motion.div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 px-4 relative overflow-hidden">
        <div className="max-w-5xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="relative rounded-3xl p-8 md:p-16 overflow-hidden border border-slate-800 bg-slate-900/50 backdrop-blur-xl text-center group"
          >
            {/* Glow Effect */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-[500px] h-[500px] bg-blue-500/20 blur-[100px] rounded-full pointer-events-none -mt-64 group-hover:bg-blue-500/30 transition-colors duration-700" />

            <h2 className="text-4xl md:text-6xl font-bold text-white mb-6 tracking-tight relative z-10">
              Ready to <span className="hero-title-gradient">transform your data?</span>
            </h2>
            <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto relative z-10">
              Join thousands of data-driven teams who are building the future of analytics. Start your free trial today.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center relative z-10">
              <Link to="/register" className="btn-premium h-14 px-8 rounded-full flex items-center justify-center gap-2 font-semibold text-lg text-white shadow-xl shadow-blue-500/20 hover:shadow-blue-500/40 transition-all">
                Start Building Now
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link to="/contact" className="h-14 px-8 rounded-full border border-slate-700 hover:bg-slate-800/50 flex items-center justify-center gap-2 font-semibold text-lg text-white transition-all">
                Talk to Sales
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-12 px-4">
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <img
                src="/logo.png"
                alt="DataSage Logo"
                className="w-6 h-6 rounded object-cover"
              />
              <span className="font-bold text-white" style={{ fontFamily: "'Rajdhani', sans-serif" }}>DataSage</span>
            </div>
            <p className="text-sm text-slate-500">
              Making data analysis accessible to everyone through the power of AI.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li><a href="#" className="hover:text-blue-400">Features</a></li>
              <li><a href="#" className="hover:text-blue-400">Integrations</a></li>
              <li><a href="#" className="hover:text-blue-400">Pricing</a></li>
              <li><a href="#" className="hover:text-blue-400">Changelog</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li><a href="#" className="hover:text-blue-400">About</a></li>
              <li><a href="#" className="hover:text-blue-400">Blog</a></li>
              <li><a href="#" className="hover:text-blue-400">Careers</a></li>
              <li><a href="#" className="hover:text-blue-400">Contact</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li><a href="#" className="hover:text-blue-400">Privacy</a></li>
              <li><a href="#" className="hover:text-blue-400">Terms</a></li>
              <li><a href="#" className="hover:text-blue-400">Security</a></li>
            </ul>
          </div>
        </div>

        <div className="max-w-7xl mx-auto pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-slate-600">
          <div>© 2024 DataSage AI Inc. All rights reserved.</div>
          <div className="flex gap-6">
            <a href="#" className="hover:text-slate-400">Twitter</a>
            <a href="#" className="hover:text-slate-400">GitHub</a>
            <a href="#" className="hover:text-slate-400">Discord</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;