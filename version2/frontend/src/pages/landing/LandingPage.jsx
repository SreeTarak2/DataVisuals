import React from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useSpring, useReducedMotion } from 'framer-motion';
import {
  ArrowRight,
  BrainCircuit,
  MessageSquareText,
  BarChart3,
  Lock,
  FileText,
  Upload,
  Eye,
  CheckCircle2,
  Sun,
  Moon,
  Star,
  Users,
  Zap,
  Sparkles,
  LineChart,
  BadgeCheck,
  Bot,
  Database,
  Shield,
  TrendingUp,
} from 'lucide-react';

import { Header as Navbar } from '@/components/ui/Header';
import Footer from '@/components/landing/Footer';
import './Landing.css';

/* ─────────────────────────────────────────────────────────────
   DATA
───────────────────────────────────────────────────────────── */

const features = [
  {
    icon: BrainCircuit,
    title: 'AI Insights Engine',
    desc: 'Statistical analysis, anomaly detection, and pattern discovery — automatically surfaced from every upload.',
  },
  {
    icon: BarChart3,
    title: 'Auto Dashboard Builder',
    desc: 'Upload a CSV and get a presentation-ready dashboard with AI-selected chart types in under 90 seconds.',
  },
  {
    icon: Lock,
    title: 'Privacy & Governance',
    desc: 'PII detection, data redaction, audit trails, and GDPR-ready export — baked in, not bolted on.',
  },
  {
    icon: FileText,
    title: 'PDF Report Export',
    desc: 'One-click professional reports with findings, charts, statistical detail, and executive summaries.',
  },
];

const workflowSteps = [
  {
    step: '01',
    icon: Upload,
    title: 'Ingest your data',
    desc: 'Upload any CSV or spreadsheet. DataSage infers structure, detects domain, and preps the data model automatically.',
  },
  {
    step: '02',
    icon: MessageSquareText,
    title: 'Ask the real question',
    desc: 'Type "what caused the Q3 dip?" in plain English. The AI understands context and finds the answer in your data.',
  },
  {
    step: '03',
    icon: Eye,
    title: 'Review a decision-ready output',
    desc: 'Get a dashboard, narrative, and recommendations — structured for your stakeholders, not your analyst.',
  },
];

const plans = [
  {
    name: 'Starter',
    tagline: 'For individuals exploring their data',
    monthlyPrice: 0,
    annualPrice: 0,
    cta: 'Get started free',
    ctaLink: '/register',
    featured: false,
    features: [
      'Up to 3 datasets',
      'Basic AI insights',
      'CSV & spreadsheet upload',
      '5 dashboard exports / month',
      'Community support',
    ],
  },
  {
    name: 'Pro',
    tagline: 'For analysts and data-driven teams',
    monthlyPrice: 29,
    annualPrice: 23,
    cta: 'Start 14-day trial',
    ctaLink: '/register',
    featured: true,
    features: [
      'Unlimited datasets',
      'Advanced AI insights + anomaly detection',
      'Natural language chat over data',
      'Unlimited dashboard exports',
      'PDF report generation',
      'Multi-agent agentic analysis',
      'Priority support',
    ],
  },
  {
    name: 'Enterprise',
    tagline: 'For teams with governance requirements',
    monthlyPrice: null,
    annualPrice: null,
    cta: 'Contact sales',
    ctaLink: '/register',
    featured: false,
    features: [
      'Everything in Pro',
      'PII detection & data redaction',
      'Full audit trail & GDPR export',
      'SSO & role-based access',
      'Custom integrations',
      'Dedicated success manager',
      'SLA guarantee',
    ],
  },
];

const testimonials = [
  {
    quote: 'DataSage cut our weekly reporting cycle from four hours to about fifteen minutes. The AI narratives are surprisingly good — our board actually reads them.',
    name: 'Sarah K.',
    role: 'VP Analytics',
    company: 'Meridian Health',
    initials: 'SK',
  },
  {
    quote: 'Finally a tool where non-analysts can get real answers without waiting in the BI queue. Our ops team now explores data independently.',
    name: 'James T.',
    role: 'CEO',
    company: 'Foundry Labs',
    initials: 'JT',
  },
  {
    quote: 'The anomaly detection flagged a margin issue three weeks before our finance team caught it. That alone paid for the subscription ten times over.',
    name: 'Priya M.',
    role: 'Operations Lead',
    company: 'NovaTech',
    initials: 'PM',
  },
];

const faqs = [
  {
    q: 'Do I need SQL or Python to use DataSage?',
    a: 'No. DataSage is designed for business users and analysts alike. You ask questions in plain English and the platform generates insights, charts, and narratives — no code required.',
  },
  {
    q: 'What file formats does DataSage support?',
    a: 'Currently CSV, Excel (.xlsx, .xls), and TSV. We auto-detect encoding, infer column types, and handle messy real-world data out of the box.',
  },
  {
    q: 'How is my data kept private?',
    a: 'Your data is encrypted at rest and in transit. Datasets are isolated per workspace. Enterprise plans include PII redaction, audit logs, and GDPR-compliant export.',
  },
  {
    q: 'Can I share or export reports?',
    a: 'Yes. You can export any dashboard or insights view as a PDF with a single click. Reports include charts, findings, statistical detail, and executive summaries.',
  },
  {
    q: 'Is there a free tier?',
    a: 'Yes. The Starter plan is free forever — up to 3 datasets with basic AI insights and CSV upload. No credit card required to get started.',
  },
  {
    q: 'What AI models power DataSage?',
    a: 'DataSage uses a multi-model router across Qwen 2.5 72B, Gemini Flash, and DeepSeek, with intelligent fallback logic to balance accuracy, speed, and cost.',
  },
];

const logoCompanies = [
  { name: 'Stripe', icon: Zap },
  { name: 'Vercel', icon: TrendingUp },
  { name: 'Linear', icon: BarChart3 },
  { name: 'Notion', icon: FileText },
  { name: 'Shopify', icon: Database },
  { name: 'Figma', icon: Sparkles },
  { name: 'Intercom', icon: MessageSquareText },
  { name: 'Loom', icon: Eye },
];

const heroMetrics = [
  { value: '< 90s', label: 'Time to first dashboard' },
  { value: '68%', label: 'Less time on reporting' },
  { value: '24/7', label: 'Questions answered in plain English' },
];

/* ─────────────────────────────────────────────────────────────
   HOOKS
───────────────────────────────────────────────────────────── */

function useScrollFade() {
  const ref = React.useRef(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('visible');
          observer.unobserve(el);
        }
      },
      { threshold: 0.08 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return ref;
}

/* ─────────────────────────────────────────────────────────────
   SUB-COMPONENTS
───────────────────────────────────────────────────────────── */

function SectionHeading({ eyebrow, title, subtitle, center = false }) {
  return (
    <div className={center ? 'mx-auto text-center' : ''} style={{ maxWidth: center ? 680 : 560 }}>
      {eyebrow && <p className="l-eyebrow mb-4">{eyebrow}</p>}
      <h2 className="l-heading-section">{title}</h2>
      {subtitle && (
        <p className="l-body mt-5" style={{ fontSize: 17 }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

function FaqItem({ question, answer, open, onToggle }) {
  return (
    <div className={`l-faq-item${open ? ' open' : ''}`}>
      <button className="l-faq-trigger" onClick={onToggle} aria-expanded={open}>
        <span>{question}</span>
        <span className="l-faq-icon" aria-hidden="true">+</span>
      </button>
      <div className="l-faq-body" role="region">
        <p className="l-faq-answer">{answer}</p>
      </div>
    </div>
  );
}

function Stars() {
  return (
    <div style={{ display: 'flex', gap: 3, color: '#FBBF24', marginBottom: 14 }}>
      {[...Array(5)].map((_, i) => (
        <Star key={i} size={13} fill="#FBBF24" />
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MAIN PAGE
───────────────────────────────────────────────────────────── */

function LandingPage() {
  const prefersReducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 28, restDelta: 0.001 });

  // Theme
  const [theme, setTheme] = React.useState(() => {
    if (typeof window === 'undefined') return 'dark';
    return localStorage.getItem('ds-landing-theme') || 'dark';
  });
  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    if (typeof window !== 'undefined') localStorage.setItem('ds-landing-theme', next);
  };

  // Pricing toggle
  const [annual, setAnnual] = React.useState(false);

  // FAQ
  const [openFaq, setOpenFaq] = React.useState(null);
  const toggleFaq = (i) => setOpenFaq((prev) => (prev === i ? null : i));

  // Scroll fade refs
  const logoRef = useScrollFade();
  const featuresRef = useScrollFade();
  const howRef = useScrollFade();
  // const pricingRef = useScrollFade();
  // const testimonialRef = useScrollFade();
  const faqRef = useScrollFade();
  const ctaRef = useScrollFade();

  return (
    <div className={`landing-v2${theme === 'light' ? ' light' : ''}`}>
      {/* Dot grid backdrop */}
      <div className="l-backdrop" aria-hidden="true" />

      {/* Scroll progress bar */}
      {!prefersReducedMotion && (
        <motion.div className="l-progress-bar" style={{ scaleX }} aria-hidden="true" />
      )}

      {/* Theme toggle (floating) */}
      <button
        className="l-theme-btn"
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <Navbar />

      <main className="relative" style={{ zIndex: 1 }}>

        {/* ═══════════════════════════════════════════════════
            1. HERO
        ════════════════════════════════════════════════════ */}
        <section
          style={{ padding: '80px 24px 96px', position: 'relative', overflow: 'hidden' }}
        >
          {/* Ambient glow */}
          <div className="l-glow-top" aria-hidden="true" />

          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            {/* Centered hero content */}
            <motion.div
              initial={prefersReducedMotion ? false : { opacity: 0, y: 24 }}
              animate={prefersReducedMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
              style={{ maxWidth: 760, margin: '0 auto', textAlign: 'center' }}
            >
              {/* Badge pill */}
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
                <span className="l-pill">
                  <span className="l-pill-dot" />
                  Now in Public Beta · Trusted by 500+ analysts
                </span>
              </div>

              {/* Headline */}
              <h1 className="l-heading-hero">
                Deep AI insights from{' '}
                <span style={{ color: 'var(--l-accent)' }}>any dataset</span>,
                instantly.
              </h1>

              {/* Subheadline */}
              <motion.p
                initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
                animate={prefersReducedMotion ? {} : { opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  maxWidth: 540,
                  margin: '20px auto 0',
                  fontSize: 19,
                  lineHeight: 1.65,
                  color: 'var(--l-text-2)',
                  fontFamily: 'var(--l-font-body)',
                }}
              >
                Upload a CSV, ask a question in plain English, get a decision-ready story.
                No SQL. No scripts. No waiting.
              </motion.p>

              {/* CTA row */}
              <motion.div
                initial={prefersReducedMotion ? false : { opacity: 0, y: 10 }}
                animate={prefersReducedMotion ? {} : { opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  display: 'flex',
                  gap: 12,
                  justifyContent: 'center',
                  flexWrap: 'wrap',
                  marginTop: 36,
                }}
              >
                <Link
                  to="/register"
                  className="l-btn l-btn-primary l-btn-lg"
                >
                  Start for free
                  <ArrowRight size={16} />
                </Link>
                <a
                  href="#how-it-works"
                  className="l-btn l-btn-secondary l-btn-lg"
                >
                  See how it works
                </a>
              </motion.div>


            </motion.div>

            {/* Hero visual — product mockup */}
            <motion.div
              initial={prefersReducedMotion ? false : { opacity: 0, y: 36 }}
              animate={prefersReducedMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.32, ease: [0.16, 1, 0.3, 1] }}
              style={{ marginTop: 64, maxWidth: 960, marginLeft: 'auto', marginRight: 'auto' }}
            >
              <div className="l-browser-frame">
                <div className="l-browser-chrome">
                  <div className="l-browser-dot" />
                  <div className="l-browser-dot" />
                  <div className="l-browser-dot" />
                  <div className="l-browser-address">app.datasage.ai / dashboard</div>
                </div>

                {/* Dashboard mockup content */}
                <div
                  style={{
                    padding: '24px',
                    background: 'var(--l-bg)',
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 1fr',
                    gap: 16,
                  }}
                >
                  {/* KPI cards */}
                  {[
                    { label: 'Revenue', value: '$4.28M', change: '+14.2%', positive: true },
                    { label: 'Conversion', value: '3.84%', change: '+0.6pp', positive: true },
                    { label: 'Churn Rate', value: '1.9%', change: '-0.3pp', positive: true },
                  ].map((kpi) => (
                    <div
                      key={kpi.label}
                      style={{
                        background: 'var(--l-bg-card)',
                        border: '1px solid var(--l-border)',
                        borderRadius: 12,
                        padding: '16px 20px',
                      }}
                    >
                      <p style={{ fontSize: 11, color: 'var(--l-text-3)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--l-font-body)' }}>
                        {kpi.label}
                      </p>
                      <p style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.04em', color: 'var(--l-text-1)', marginTop: 6, fontFamily: 'var(--l-font-display)' }}>
                        {kpi.value}
                      </p>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          marginTop: 8,
                          fontSize: 12,
                          fontWeight: 500,
                          color: kpi.positive ? '#34D399' : '#F87171',
                          background: kpi.positive ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
                          padding: '2px 8px',
                          borderRadius: 999,
                        }}
                      >
                        {kpi.change}
                      </span>
                    </div>
                  ))}

                  {/* Chart panel */}
                  <div
                    style={{
                      background: 'var(--l-bg-card)',
                      border: '1px solid var(--l-border)',
                      borderRadius: 12,
                      padding: '20px',
                      gridColumn: 'span 2',
                    }}
                  >
                    <p style={{ fontSize: 12, color: 'var(--l-text-3)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 16, fontFamily: 'var(--l-font-body)' }}>
                      Revenue trend — Last 12 months
                    </p>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height: 72 }}>
                      {[34, 48, 38, 55, 50, 66, 72, 61, 80, 74, 88, 82].map((h, i) => (
                        <div key={i} style={{ flex: 1 }}>
                          <div
                            style={{
                              height: `${h}%`,
                              borderRadius: '4px 4px 0 0',
                              background: i > 8
                                ? 'var(--l-accent)'
                                : 'var(--l-border-strong)',
                              opacity: i > 8 ? 1 : 0.5,
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* AI narrative card */}
                  <div
                    style={{
                      background: 'var(--l-bg-card)',
                      border: '1px solid var(--l-border)',
                      borderRadius: 12,
                      padding: '20px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <div className="l-icon-box" style={{ width: 28, height: 28, borderRadius: 8 }}>
                        <Sparkles size={13} />
                      </div>
                      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--l-text-2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        AI Insight
                      </p>
                    </div>
                    <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--l-text-1)' }}>
                      Mid-market expansion drove renewal growth, offsetting new-logo softness in Q4.
                    </p>
                    <div
                      style={{
                        marginTop: 12,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        fontSize: 12,
                        color: '#34D399',
                        background: 'rgba(52,211,153,0.08)',
                        padding: '6px 10px',
                        borderRadius: 8,
                      }}
                    >
                      <BadgeCheck size={13} />
                      Confidence: 92%
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Metrics strip */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 1,
                maxWidth: 640,
                margin: '48px auto 0',
                borderRadius: 16,
                border: '1px solid var(--l-border)',
                overflow: 'hidden',
                background: 'var(--l-border)',
              }}
            >
              {heroMetrics.map((m) => (
                <div
                  key={m.label}
                  style={{
                    background: 'var(--l-bg-card)',
                    padding: '20px 24px',
                    textAlign: 'center',
                  }}
                >
                  <p
                    style={{
                      fontFamily: 'var(--l-font-display)',
                      fontSize: 26,
                      fontWeight: 700,
                      letterSpacing: '-0.04em',
                      color: 'var(--l-text-1)',
                    }}
                  >
                    {m.value}
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--l-text-3)', marginTop: 6, fontFamily: 'var(--l-font-body)' }}>
                    {m.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════
            2. LOGO BAR
        ════════════════════════════════════════════════════ */}
        <section ref={logoRef} className="l-fade" style={{ padding: '40px 0', borderTop: '1px solid var(--l-border)', borderBottom: '1px solid var(--l-border)' }}>
          <p
            style={{
              textAlign: 'center',
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--l-text-3)',
              marginBottom: 28,
              fontFamily: 'var(--l-font-body)',
            }}
          >
            Trusted by teams at
          </p>

          <div className="l-marquee-wrap">
            <div className="l-marquee-track">
              {/* Duplicate for seamless loop */}
              {[...logoCompanies, ...logoCompanies].map(({ name, icon: Icon }, i) => (
                <span key={`${name}-${i}`} className="l-logo-item">
                  <Icon size={16} />
                  {name}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════
            3. FEATURES GRID
        ════════════════════════════════════════════════════ */}
        <section
          id="features"
          ref={featuresRef}
          className="l-fade"
          style={{ padding: '120px 24px', maxWidth: 1200, margin: '0 auto' }}
        >
          <SectionHeading
            eyebrow="Platform capabilities"
            title="Everything you need to go from raw data to real decisions."
            subtitle="DataSage combines statistical rigor, agentic AI, and a clean editorial interface — so every team can move faster with confidence."
            center
          />

          <div
            className="l-grid-features"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 16,
              marginTop: 56,
            }}
          >
            {/* Regular feature cards (4) */}
            {features.map((f, i) => (
              <div
                key={f.title}
                className="l-card l-card-featured"
                style={{ padding: 28 }}
              >
                <div className="l-icon-box">
                  <f.icon size={18} />
                </div>
                <h3
                  style={{
                    fontFamily: 'var(--l-font-body)',
                    fontSize: 16,
                    fontWeight: 600,
                    color: 'var(--l-text-1)',
                    marginTop: 20,
                  }}
                >
                  {f.title}
                </h3>
                <p className="l-body-sm" style={{ marginTop: 10 }}>
                  {f.desc}
                </p>
              </div>
            ))}

            {/* Spotlight card — spans 2 cols */}
            <div
              className="l-spotlight-card l-spotlight-span"
              style={{ gridColumn: 'span 2', padding: 28, display: 'flex', flexDirection: 'column', gap: 0 }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20 }}>
                <div style={{ flex: 1 }}>
                  <div className="l-icon-box">
                    <MessageSquareText size={18} />
                  </div>
                  <h3
                    style={{
                      fontFamily: 'var(--l-font-body)',
                      fontSize: 17,
                      fontWeight: 600,
                      color: 'var(--l-text-1)',
                      marginTop: 20,
                    }}
                  >
                    Natural Language Chat
                  </h3>
                  <p className="l-body-sm" style={{ marginTop: 10, maxWidth: 340 }}>
                    Ask questions about your data the way you would ask a colleague. The multi-agent system reasons, cross-references, and responds with cited evidence.
                  </p>
                </div>
                {/* Mini chat mockup */}
                <div
                  style={{
                    flex: 1,
                    background: 'var(--l-bg)',
                    border: '1px solid var(--l-border)',
                    borderRadius: 14,
                    padding: 16,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    maxWidth: 320,
                  }}
                >
                  <div className="l-chat-bubble user">
                    What caused the revenue dip in March?
                  </div>
                  <div className="l-chat-bubble ai">
                    <strong>March dip was driven by two factors:</strong> a 3-week delay in enterprise renewals (−$180K) and a regional pricing change in APAC (−$94K). Both are now recovered as of April 7th.
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="l-icon-box" style={{ width: 24, height: 24, borderRadius: 6 }}>
                      <Sparkles size={11} />
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--l-text-3)', fontFamily: 'var(--l-font-body)' }}>
                      DataSage AI · Confidence 89%
                    </span>
                  </div>
                </div>
              </div>

              {/* Feature bullets */}
              <div
                style={{
                  display: 'flex',
                  gap: 20,
                  flexWrap: 'wrap',
                  marginTop: 28,
                  paddingTop: 24,
                  borderTop: '1px solid var(--l-border)',
                }}
              >
                {['Multi-turn memory', 'Source citation', 'Follow-up suggestions', 'Belief-aware context'].map((item) => (
                  <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--l-text-2)' }}>
                    <CheckCircle2 size={14} style={{ color: 'var(--l-accent)', flexShrink: 0 }} />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <div style={{ maxWidth: 1200, margin: '0 auto 0', padding: '0 24px' }}>
          <div className="l-divider" />
        </div>

        {/* ═══════════════════════════════════════════════════
            4. HOW IT WORKS
        ════════════════════════════════════════════════════ */}
        <section
          id="how-it-works"
          ref={howRef}
          className="l-fade"
          style={{ padding: '120px 24px' }}
        >
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <SectionHeading
              eyebrow="How it works"
              title="From raw file to executive narrative in three steps."
              subtitle="No setup, no configuration, no data engineering. Just upload, ask, and share."
              center
            />

            {/* Steps */}
            <div
              className="l-grid-how"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 0,
                marginTop: 64,
                position: 'relative',
              }}
            >
              {/* Connector lines (desktop) */}
              <div
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  top: 22,
                  left: 'calc(33.33% - 40px)',
                  right: 'calc(33.33% - 40px)',
                  height: 1,
                  background: 'linear-gradient(to right, var(--l-accent), var(--l-border))',
                  opacity: 0.3,
                  pointerEvents: 'none',
                }}
              />

              {workflowSteps.map((step, i) => (
                <div key={step.step} style={{ padding: '0 24px', textAlign: 'center' }}>
                  {/* Number circle */}
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
                    <div className="l-step-number">{step.step}</div>
                  </div>

                  <div
                    className="l-icon-box"
                    style={{ margin: '0 auto 20px', width: 48, height: 48, borderRadius: 14 }}
                  >
                    <step.icon size={20} />
                  </div>

                  <h3
                    style={{
                      fontFamily: 'var(--l-font-display)',
                      fontSize: 18,
                      fontWeight: 600,
                      color: 'var(--l-text-1)',
                      letterSpacing: '-0.02em',
                      marginBottom: 12,
                    }}
                  >
                    {step.title}
                  </h3>
                  <p className="l-body-sm" style={{ maxWidth: 260, margin: '0 auto' }}>
                    {step.desc}
                  </p>
                </div>
              ))}
            </div>

            {/* CTA under steps */}
            <div style={{ textAlign: 'center', marginTop: 56 }}>
              <Link to="/register" className="l-btn l-btn-primary">
                Try it free — no credit card
                <ArrowRight size={15} />
              </Link>
            </div>
          </div>
        </section>

        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <div className="l-divider" />
        </div>

        {/* ═══════════════════════════════════════════════════
            5. PRICING (Commented out for Major Project)
        ════════════════════════════════════════════════════ */}
        {/* <section
          ref={pricingRef}
          className="l-fade"
          style={{ padding: '120px 24px' }}
        >
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <SectionHeading
              eyebrow="Pricing"
              title="Simple, transparent pricing."
              subtitle="Start free. Upgrade when you're ready. No hidden fees."
              center
            />

            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 32 }}>
              <div className="l-toggle-wrap">
                <button
                  className={`l-toggle-btn${!annual ? ' active' : ''}`}
                  onClick={() => setAnnual(false)}
                >
                  Monthly
                </button>
                <button
                  className={`l-toggle-btn${annual ? ' active' : ''}`}
                  onClick={() => setAnnual(true)}
                >
                  Annual
                </button>
              </div>
              {annual && (
                <span className="l-savings-badge">Save 20%</span>
              )}
            </div>

            <div
              className="l-grid-pricing"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 16,
                marginTop: 48,
                alignItems: 'start',
              }}
            >
              {plans.map((plan) => (
                <div
                  key={plan.name}
                  className={`l-pricing-card${plan.featured ? ' featured' : ''}`}
                >
                  {plan.featured && (
                    <div className="l-pricing-badge">Most popular</div>
                  )}

                  <div>
                    <p
                      style={{
                        fontFamily: 'var(--l-font-display)',
                        fontSize: 18,
                        fontWeight: 700,
                        color: 'var(--l-text-1)',
                        letterSpacing: '-0.02em',
                      }}
                    >
                      {plan.name}
                    </p>
                    <p style={{ fontSize: 13, color: 'var(--l-text-2)', marginTop: 6, fontFamily: 'var(--l-font-body)' }}>
                      {plan.tagline}
                    </p>
                  </div>

                  <div style={{ margin: '24px 0' }}>
                    {plan.monthlyPrice === null ? (
                      <p className="l-price-amount">Custom</p>
                    ) : plan.monthlyPrice === 0 ? (
                      <p className="l-price-amount">Free</p>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                        <span className="l-price-amount">
                          ${annual ? plan.annualPrice : plan.monthlyPrice}
                        </span>
                        <span style={{ fontSize: 14, color: 'var(--l-text-2)' }}>/month</span>
                      </div>
                    )}
                    {annual && plan.monthlyPrice !== null && plan.monthlyPrice > 0 && (
                      <p style={{ fontSize: 12, color: 'var(--l-text-3)', marginTop: 4 }}>
                        Billed annually · ${plan.annualPrice * 12}/year
                      </p>
                    )}
                  </div>

                  <Link
                    to={plan.ctaLink}
                    className={`l-btn${plan.featured ? ' l-btn-primary' : ' l-btn-secondary'}`}
                    style={{ width: '100%', justifyContent: 'center', marginBottom: 28, borderRadius: 10 }}
                  >
                    {plan.cta}
                  </Link>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {plan.features.map((feat) => (
                      <div key={feat} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                        <CheckCircle2
                          size={15}
                          style={{ color: 'var(--l-accent)', flexShrink: 0, marginTop: 1 }}
                        />
                        <span style={{ fontSize: 14, color: 'var(--l-text-2)', lineHeight: 1.5, fontFamily: 'var(--l-font-body)' }}>
                          {feat}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section> */}

        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <div className="l-divider" />
        </div>

        {/* ═══════════════════════════════════════════════════
            6. TESTIMONIALS (Commented out for Major Project)
        ════════════════════════════════════════════════════ */}
        {/* <section
          ref={testimonialRef}
          className="l-fade"
          style={{ padding: '120px 24px' }}
        >
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <SectionHeading
              eyebrow="What teams say"
              title="Trusted by analysts, loved by executives."
              center
            />

            <div
              className="l-grid-testimonials"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 20,
                marginTop: 56,
              }}
            >
              {testimonials.map((t) => (
                <div key={t.name} className="l-testimonial">
                  <Stars />
                  <p
                    style={{
                      fontSize: 15,
                      lineHeight: 1.72,
                      color: 'var(--l-text-1)',
                      fontStyle: 'italic',
                    }}
                  >
                    "{t.quote}"
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 20 }}>
                    <div className="l-avatar">{t.initials}</div>
                    <div>
                      <p
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: 'var(--l-text-1)',
                          fontFamily: 'var(--l-font-body)',
                        }}
                      >
                        {t.name}
                      </p>
                      <p style={{ fontSize: 12, color: 'var(--l-text-3)', marginTop: 2 }}>
                        {t.role} · {t.company}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section> */}

        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <div className="l-divider" />
        </div>

        {/* ═══════════════════════════════════════════════════
            7. FAQ
        ════════════════════════════════════════════════════ */}
        <section
          id="faq"
          ref={faqRef}
          className="l-fade"
          style={{ padding: '120px 24px' }}
        >
          <div
            className="l-grid-faq"
            style={{
              maxWidth: 1200,
              margin: '0 auto',
              display: 'grid',
              gridTemplateColumns: '1fr 1.4fr',
              gap: 64,
              alignItems: 'start',
            }}
          >
            <div>
              <SectionHeading
                eyebrow="FAQ"
                title="Everything you need to know."
                subtitle="Can't find an answer? Reach out to our team — we respond within one business day."
              />
              <div style={{ marginTop: 28 }}>
                <Link to="/register" className="l-btn l-btn-secondary" style={{ borderRadius: 10 }}>
                  Contact support
                </Link>
              </div>
            </div>

            <div>
              {faqs.map((item, i) => (
                <FaqItem
                  key={item.q}
                  question={item.q}
                  answer={item.a}
                  open={openFaq === i}
                  onToggle={() => toggleFaq(i)}
                />
              ))}
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════
            8. FINAL CTA
        ════════════════════════════════════════════════════ */}
        <section
          ref={ctaRef}
          className="l-fade"
          style={{ padding: '0 24px 120px' }}
        >
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div className="l-cta-bg" style={{ padding: '72px 64px', position: 'relative' }}>
              {/* Noise/pattern overlay handled by CSS ::after */}
              <div
                style={{
                  position: 'relative',
                  zIndex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  gap: 0,
                }}
              >
                <p
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.65)',
                    marginBottom: 20,
                    fontFamily: 'var(--l-font-body)',
                  }}
                >
                  Start for free today
                </p>

                <h2
                  style={{
                    fontFamily: 'var(--l-font-display)',
                    fontSize: 'clamp(30px, 4.5vw, 52px)',
                    fontWeight: 700,
                    letterSpacing: '-0.03em',
                    lineHeight: 1.06,
                    color: '#ffffff',
                    maxWidth: 600,
                  }}
                >
                  Give your data the analysis it deserves.
                </h2>

                <p
                  style={{
                    fontSize: 18,
                    lineHeight: 1.65,
                    color: 'rgba(255,255,255,0.75)',
                    maxWidth: 480,
                    marginTop: 20,
                    fontFamily: 'var(--l-font-body)',
                  }}
                >
                  No SQL. No scripts. No waiting. Just upload, ask, and get decisions.
                </p>

                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center', marginTop: 40 }}>
                  <Link
                    to="/register"
                    className="l-btn l-btn-lg"
                    style={{
                      background: '#ffffff',
                      color: '#4340E8',
                      fontWeight: 600,
                      borderRadius: 14,
                    }}
                  >
                    Get started free
                    <ArrowRight size={16} />
                  </Link>
                  <Link
                    to="/login"
                    className="l-btn l-btn-ghost l-btn-lg"
                    style={{ borderRadius: 14 }}
                  >
                    Sign in
                  </Link>
                </div>

                <p
                  style={{
                    fontSize: 12,
                    color: 'rgba(255,255,255,0.45)',
                    marginTop: 20,
                    fontFamily: 'var(--l-font-body)',
                  }}
                >
                  Free forever · No credit card required · Cancel anytime
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}

export default LandingPage;
