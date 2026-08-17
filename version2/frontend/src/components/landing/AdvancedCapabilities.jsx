import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, BarChart3, Code2 } from 'lucide-react';

const ACCENT = '#F97316';
const ACCENT_SOFT = 'rgba(249,115,22,0.1)';
const ACCENT_BORDER = 'rgba(249,115,22,0.25)';

const CapabilityRow = ({ icon, title, description, bullets, visual, reverse }) => {
    const Icon = icon;
    return (
        <div className={`grid md:grid-cols-2 gap-12 lg:gap-24 items-center mb-24 text-left ${reverse ? '' : ''}`}>
            <motion.div
                initial={{ opacity: 0, x: reverse ? 40 : -40 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className={reverse ? 'md:order-2' : ''}
            >
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-6 border"
                    style={{ background: ACCENT_SOFT, border: `1px solid ${ACCENT_BORDER}`, color: ACCENT }}>
                    <Icon className="w-6 h-6" />
                </div>
                <h3 className="text-2xl md:text-3xl font-bold mb-4 text-white tracking-tight">{title}</h3>
                <p className="text-neutral-400 text-lg leading-relaxed mb-6">{description}</p>
                {bullets && (
                    <ul className="space-y-3">
                        {bullets.map((item, i) => (
                            <li key={i} className="flex items-center gap-3 text-neutral-300 pointer-events-none">
                                <div className="w-1.5 h-1.5 rounded-full" style={{ background: ACCENT }} />
                                {item}
                            </li>
                        ))}
                    </ul>
                )}
            </motion.div>
            <motion.div
                initial={{ opacity: 0, x: reverse ? -40 : 40 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className={reverse ? 'md:order-1' : ''}
            >
                {visual}
            </motion.div>
        </div>
    );
};

const AdvancedCapabilities = () => {
    return (
        <section id="capabilities" className="py-32 relative bg-[#0A0A0A] overflow-hidden">
            {/* Warm background glows */}
            <div className="absolute right-0 top-0 w-1/2 h-1/2 rounded-full -z-10" style={{ background: 'rgba(249,115,22,0.05)', filter: 'blur(150px)' }} />
            <div className="absolute left-0 bottom-0 w-1/2 h-1/2 rounded-full -z-10" style={{ background: 'rgba(249,115,22,0.04)', filter: 'blur(150px)' }} />

            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-24 max-w-3xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5"
                        style={{ color: ACCENT }}
                    >
                        Deeper capabilities
                    </motion.div>
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white"
                    >
                        Beyond bar charts and generic answers.
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="text-lg md:text-xl text-neutral-400"
                    >
                        Signal doesn't just answer — it reasons about the shape of your data and shows its work.
                    </motion.p>
                </div>

                {/* 1 — Automated insights */}
                <CapabilityRow
                    icon={Sparkles}
                    title="An insight engine that works before you ask"
                    description="The QUIS engine scans your dataset for anomalies, correlations, and segment behavior, then synthesizes findings into an executive summary — flagged with confidence, not certainty."
                    bullets={['Anomaly detection with confidence intervals', 'Cohort & segment behavior analysis', 'Trend and period-over-period comparison']}
                    reverse={false}
                    visual={
                        <div className="aspect-[4/3] rounded-2xl border border-white/[0.05] bg-[#0D0D0F] flex flex-col justify-center relative shadow-2xl overflow-hidden p-8">
                            <div className="absolute inset-x-0 bottom-0 h-1/2" style={{ background: 'linear-gradient(to top, rgba(249,115,22,0.1), transparent)' }} />
                            <div className="space-y-4 w-full">
                                <div className="h-4 w-1/3 bg-white/5 rounded" />
                                <div className="h-4 w-full bg-white/5 rounded" />
                                <div className="flex items-end gap-3 h-24 mt-6">
                                    {[40, 70, 45, 90, 60, 100, 55, 80].map((h, i) => (
                                        <div key={i} className="flex-1 rounded-t-md relative"
                                            style={{ height: `${h}%`, background: i === 5 ? ACCENT : 'rgba(249,115,22,0.25)' }}>
                                            {i === 5 && (
                                                <div className="absolute -top-9 left-1/2 -translate-x-1/2 bg-white text-black text-[10px] font-bold py-1 px-2 rounded whitespace-nowrap">
                                                    Anomaly ±2.1
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    }
                />

                {/* 2 — Chart intelligence */}
                <CapabilityRow
                    icon={BarChart3}
                    title="The right chart, chosen for your data"
                    description="No 'select chart type' dropdown. Signal evaluates your schema, cardinality, and relationships and recommends the visualization that actually fits — funnel, sunburst, scatter, or time series."
                    bullets={['Schema-aware chart recommendation', 'Semantic type detection (currency, dates, ratios)', 'Consistent styling across every chart']}
                    reverse={true}
                    visual={
                        <div className="aspect-[4/3] rounded-2xl border border-white/[0.05] bg-[#0D0D0F] flex items-center justify-center relative shadow-2xl overflow-hidden">
                            <div className="absolute inset-0" style={{ background: 'linear-gradient(to top right, rgba(249,115,22,0.05), transparent)' }} />
                            <div className="w-3/4 h-3/4 flex gap-4 items-end justify-center">
                                {[40, 70, 45, 90, 60, 100].map((h, i) => (
                                    <div key={i} className="w-8 rounded-t-md relative flex-shrink-0" style={{ height: `${h}%`, background: i === 3 ? ACCENT : 'rgba(249,115,22,0.35)' }}>
                                        {i === 3 && (
                                            <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-white text-black text-[10px] font-bold py-1 px-2 rounded whitespace-nowrap">
                                                Recommended: bar
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    }
                />

                {/* 3 — Show your work */}
                <CapabilityRow
                    icon={Code2}
                    title="Every answer shows its work"
                    description="Each insight carries the metric definition it used, the SQL that produced it, and the row counts behind it. Analysts can audit, copy, and refine — or hand the SQL to the built-in editor."
                    bullets={['SQL provenance on every answer', 'Full SQL editor with history and sharing', 'Metric definitions you can edit once, use everywhere']}
                    reverse={false}
                    visual={
                        <div className="aspect-[4/3] rounded-2xl border border-white/[0.05] bg-[#0D0D0F] shadow-2xl overflow-hidden flex flex-col">
                            <div className="px-5 py-3 border-b border-white/[0.05] flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="flex gap-1.5">
                                        <div className="w-2.5 h-2.5 rounded-full bg-neutral-800 border border-white/5" />
                                        <div className="w-2.5 h-2.5 rounded-full bg-neutral-800 border border-white/5" />
                                        <div className="w-2.5 h-2.5 rounded-full bg-neutral-800 border border-white/5" />
                                    </div>
                                    <span className="text-[10px] text-neutral-500 font-mono ml-2">query_1024.sql</span>
                                </div>
                                <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: ACCENT_SOFT, color: ACCENT }}>verified</span>
                            </div>
                            <div className="flex-1 p-5 font-mono text-[12px] leading-relaxed text-neutral-300 overflow-hidden">
                                <div><span style={{ color: ACCENT }}>SELECT</span> date_trunc('day', created_at) <span style={{ color: ACCENT }}>AS</span> day,</div>
                                <div className="pl-4"><span style={{ color: ACCENT }}>SUM</span>(net_revenue) <span style={{ color: ACCENT }}>AS</span> revenue</div>
                                <div><span style={{ color: ACCENT }}>FROM</span> orders</div>
                                <div><span style={{ color: ACCENT }}>WHERE</span> status = 'paid'</div>
                                <div><span style={{ color: ACCENT }}>GROUP BY</span> 1</div>
                                <div><span style={{ color: ACCENT }}>ORDER BY</span> day</div>
                                <div className="mt-4 pt-3 border-t border-white/[0.05] text-neutral-500">
                                    <span className="text-emerald-500">✓</span> 1,284,302 rows · net_revenue = "revenue − refunds" <span className="text-neutral-600">(your definition)</span>
                                </div>
                            </div>
                        </div>
                    }
                />
            </div>
        </section>
    );
};

export default AdvancedCapabilities;
