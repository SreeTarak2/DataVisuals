import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { MessageSquareText, LayoutDashboard, Database, Activity, BrainCircuit, ShieldCheck } from 'lucide-react';

const ACCENT = '#F97316';

const FeatureCard = ({ icon, title, description, className, index, tag }) => {
    const Icon = icon;
    const prefersReducedMotion = useReducedMotion();

    return (
        <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : index * 0.1, ease: 'easeOut' }}
            viewport={{ once: true, margin: "-50px" }}
            className={`p-8 group ${className}`}
        >
            <div className="w-10 h-10 flex items-center justify-center mb-6 transition-transform duration-300 group-hover:-translate-y-1 rounded-lg border"
                style={{ background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.25)', color: ACCENT }}>
                <Icon className="w-5 h-5" aria-hidden="true" />
            </div>
            {tag && (
                <div className="mb-3 text-[10px] font-bold uppercase tracking-widest" style={{ color: ACCENT }}>{tag}</div>
            )}
            <h3 className="text-xl font-bold text-white mb-3 tracking-tight">{title}</h3>
            <p className="text-neutral-400 leading-relaxed text-balance">{description}</p>
        </motion.div>
    );
};

const FeatureBento = () => {
    return (
        <section id="features" className="py-32 relative border-t border-white/[0.03]">
            <div className="container mx-auto px-6">
                <div className="text-center max-w-3xl mx-auto mb-20">
                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5" style={{ color: ACCENT }}>The platform</div>
                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 tracking-tight text-balance">
                        Everything between your data and a decision.
                    </h2>
                    <p className="text-lg text-neutral-400">
                        No dashboards to wire by hand. No SQL to memorize. No context to re-explain every week.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-hidden">
                    {/* Large card — AI chat */}
                    <FeatureCard
                        icon={MessageSquareText}
                        tag="AI chat"
                        title="Ask in plain English. Get answers with receipts."
                        description="Chat with your data and watch the answer stream in — along with the SQL behind it. Every number cites its definition, so trust is automatic, not assumed."
                        className="md:col-span-2 md:row-span-2 bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={0}
                    />

                    {/* Dashboards */}
                    <FeatureCard
                        icon={LayoutDashboard}
                        tag="Dashboards"
                        title="One-click executive dashboards"
                        description="KPI cards, charts, and trend analysis generated from your data — then fine-tuned by dragging and asking."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={1}
                    />

                    {/* Connectors */}
                    <FeatureCard
                        icon={Database}
                        tag="Connectors"
                        title="Connect where your data lives"
                        description="Postgres, MySQL, MongoDB, Supabase, Google Sheets, and Excel — plus a dlt-powered catalog for SaaS sources like Stripe and Zendesk."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={2}
                    />

                    {/* Insight engine */}
                    <FeatureCard
                        icon={Activity}
                        tag="Insight engine"
                        title="Anomalies found before you ask"
                        description="The QUIS engine scans for outliers, correlations, and segment behavior — with confidence intervals instead of confident guesses."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={3}
                    />

                    {/* Memory */}
                    <FeatureCard
                        icon={BrainCircuit}
                        tag="Memory"
                        title="It remembers how you define things"
                        description="Correct an answer once — 'Revenue means net, not bookings' — and every future answer uses your definition. Context compounds."
                        className="md:col-span-2 bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={4}
                    />

                    {/* Security */}
                    <FeatureCard
                        icon={ShieldCheck}
                        tag="Security"
                        title="Your data stays yours"
                        description="PII detection and redaction, encrypted database credentials, and your data is never used to train public models."
                        className="bg-[#0D0D0F] border border-white/5 rounded-2xl"
                        index={5}
                    />
                </div>
            </div>
        </section>
    );
};

export default FeatureBento;
