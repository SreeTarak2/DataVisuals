import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  ArrowRight, MessageSquareText, LayoutDashboard, Database, Activity,
  BrainCircuit, ShieldCheck, Code2, BellRing, FileText
} from 'lucide-react';
import SubPageLayout from '@/components/landing/SubPageLayout';

const ACCENT = '#F97316';
const ACCENT_SOFT = 'rgba(249,115,22,0.08)';
const ACCENT_BORDER = 'rgba(249,115,22,0.22)';

const Feature = ({ icon, title, description, index }) => {
  const Icon = icon;
  const prefersReducedMotion = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: prefersReducedMotion ? 0 : (index % 3) * 0.08 }}
      viewport={{ once: true, margin: "-40px" }}
      className="lp-card lp-card--hover p-8"
    >
      <div className="lp-icon-tile mb-5">
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="text-lg font-bold text-white mb-2 tracking-tight">{title}</h3>
      <p className="text-sm text-neutral-400 leading-relaxed">{description}</p>
    </motion.div>
  );
};

const FeaturesPage = () => {
  return (
    <SubPageLayout>
      {/* Header */}
      <div className="lp-page-header">
        <div className="lp-wrapper">
          <div className="lp-crumbs">
            <Link to="/">Home</Link> <span>/</span> <span>Features</span>
          </div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-4" style={{ color: ACCENT }}>
            Features
          </div>
          <h1 className="lp-title mb-5">The full platform, in one place.</h1>
          <p className="lp-subtitle">
            From natural-language queries to governed metric definitions — every layer of Signal is built to
            make your data team faster and your answers more trustworthy.
          </p>
        </div>
      </div>

      {/* Feature grid */}
      <section className="py-20">
        <div className="lp-wrapper">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Feature
              index={0}
              icon={MessageSquareText}
              title="AI chat that writes the SQL"
              description="Ask in plain English. Signal writes and runs the SQL on DuckDB, streams the answer, and charts it — with follow-up suggestions and message versioning."
            />
            <Feature
              index={1}
              icon={LayoutDashboard}
              title="One-click dashboards"
              description="KPI cards, trend analysis, and recommended charts generated from your data. Drag, resize, and ask for redesigns in plain language."
            />
            <Feature
              index={2}
              icon={Database}
              title="Live data connectors"
              description="Postgres, MySQL, MongoDB, Supabase, Google Sheets, and Excel — plus a dlt-powered catalog for Stripe, Zendesk, Shopify, and more."
            />
            <Feature
              index={3}
              icon={Activity}
              title="Insight engine (QUIS)"
              description="Automatic anomaly detection, cohort behavior, correlations, and segment analysis — each finding qualified with confidence intervals."
            />
            <Feature
              index={4}
              icon={BrainCircuit}
              title="Belief store & memory"
              description="Corrections become lasting knowledge. Metric definitions, terminology, and preferences persist per team and improve every future answer."
            />
            <Feature
              index={5}
              icon={Code2}
              title="SQL editor & provenance"
              description="Every answer shows its SQL. Open it in a full editor with history, sharing, and CSV/JSON export — or hand it to your own tools."
            />
            <Feature
              index={6}
              icon={BellRing}
              title="Scheduled reports & alerts"
              description="Proactive notifications and scheduled reports keep your team ahead of anomalies — without anyone writing a query."
            />
            <Feature
              index={7}
              icon={FileText}
              title="Data briefings"
              description="A generated briefing per dataset: primary object, entity relationships, reference signals, and the questions worth asking first."
            />
            <Feature
              index={8}
              icon={ShieldCheck}
              title="Security & governance"
              description="PII detection and redaction, encrypted credentials, per-user budget caps, role-based permissions, and audit logging."
            />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-white/[0.03]">
        <div className="lp-wrapper">
          <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] p-12 md:p-16 text-center">
            <div className="absolute inset-0 lp-glow-orange pointer-events-none" />
            <div className="relative z-10">
              <h2 className="text-2xl md:text-4xl font-extrabold text-white mb-4 tracking-tight">Try every feature, free.</h2>
              <p className="text-neutral-400 mb-8 max-w-md mx-auto">Upload a file or connect a database. No credit card.</p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link to="/register" className="lp-btn lp-btn-primary lp-btn-lg">
                  Start free <ArrowRight size={16} />
                </Link>
                <Link to="/demo" className="lp-btn lp-btn-outline lp-btn-lg">Book a demo</Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </SubPageLayout>
  );
};

export default FeaturesPage;
