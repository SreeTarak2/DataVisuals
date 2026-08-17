import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { CheckCircle2, BookMarked, FileSearch, RefreshCcw } from 'lucide-react';

const ACCENT = '#F97316';
const ACCENT_SOFT = 'rgba(249,115,22,0.08)';
const ACCENT_BORDER = 'rgba(249,115,22,0.22)';

const ProofCard = ({ icon, title, description, children, index }) => {
    const Icon = icon;
    const prefersReducedMotion = useReducedMotion();

    return (
        <motion.div
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : index * 0.1, ease: 'easeOut' }}
            viewport={{ once: true, margin: "-50px" }}
            className="bg-[#0D0D0F] border border-white/5 rounded-2xl p-8 flex flex-col gap-6"
        >
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg border flex items-center justify-center"
                    style={{ background: ACCENT_SOFT, border: `1px solid ${ACCENT_BORDER}`, color: ACCENT }}>
                    <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white tracking-tight">{title}</h3>
            </div>
            <p className="text-sm text-neutral-400 leading-relaxed -mt-3">{description}</p>
            {children}
        </motion.div>
    );
};

const ProofSection = () => {
    return (
        <section id="proof" className="py-32 relative bg-[#0A0A0A]">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-20">
                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5" style={{ color: ACCENT }}>
                        Proof, not promises
                    </div>
                    <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white text-balance">
                        You don't have to take our word for it.
                    </h2>
                    <p className="text-lg text-neutral-400 max-w-2xl mx-auto">
                        The AI-analytics market is full of confident wrong answers. Here is exactly how Signal earns trust — with machinery you can audit, not copy we made up.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-6">
                    {/* 1 — Correction loop */}
                    <ProofCard
                        icon={RefreshCcw}
                        title="Corrections compound"
                        description="Teach it once and the belief store keeps the lesson — across sessions, for your whole team."
                        index={0}
                    >
                        <div className="rounded-xl border border-white/[0.06] bg-[#0B0B0D] p-4 space-y-3 text-[12px]">
                            <div className="flex items-start gap-2">
                                <div className="w-5 h-5 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-[9px] text-neutral-400 flex-shrink-0 mt-0.5">U</div>
                                <p className="text-neutral-300">"Revenue was $112k — but that includes refunds. Use net."</p>
                            </div>
                            <div className="flex items-start gap-2 pl-7">
                                <p className="text-neutral-500 text-[11px] italic">Saved to belief store · applies to all future answers</p>
                            </div>
                            <div className="flex items-start gap-2 pt-2 border-t border-white/[0.05]">
                                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] text-white flex-shrink-0 mt-0.5" style={{ background: ACCENT }}>S</div>
                                <p className="text-neutral-300">"Net revenue last quarter: <span className="text-white font-semibold">$98,410</span> — using net, per your definition."</p>
                            </div>
                        </div>
                    </ProofCard>

                    {/* 2 — Governed metrics */}
                    <ProofCard
                        icon={BookMarked}
                        title="Definitions you control"
                        description="Your team's metric definitions live in one place — not in a model's hidden weights."
                        index={1}
                    >
                        <div className="rounded-xl border border-white/[0.06] bg-[#0B0B0D] p-4 space-y-2 text-[12px]">
                            {[
                                { name: 'Net Revenue', def: 'revenue − refunds' },
                                { name: 'Active Customer', def: 'paid & active in 30d' },
                                { name: 'Conversion Rate', def: 'signups / sessions' },
                            ].map((m) => (
                                <div key={m.name} className="flex items-center justify-between gap-3 py-1.5 border-b border-white/[0.04] last:border-0">
                                    <div className="flex items-center gap-2 min-w-0">
                                        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" style={{ color: ACCENT }} />
                                        <span className="text-neutral-200 font-medium truncate">{m.name}</span>
                                    </div>
                                    <div className="flex-shrink-0">
                                        <span className="text-neutral-400 font-mono text-[11px]">{m.def}</span>
                                    </div>
                                </div>
                            ))}
                            <p className="pt-2 text-[11px] text-neutral-500 italic leading-relaxed">
                                Stored per workspace — every future answer uses the same definition, in every conversation.
                            </p>
                        </div>
                    </ProofCard>

                    {/* 3 — Show your work */}
                    <ProofCard
                        icon={FileSearch}
                        title="Answers show their work"
                        description="Every number carries the SQL, the metric definition, and the row count behind it."
                        index={2}
                    >
                        <div className="rounded-xl border border-white/[0.06] bg-[#0B0B0D] p-4 text-[12px] font-mono text-neutral-300 space-y-1">
                            <div><span style={{ color: ACCENT }}>SELECT</span> region, <span style={{ color: ACCENT }}>SUM</span>(net_revenue)</div>
                            <div><span style={{ color: ACCENT }}>FROM</span> orders <span style={{ color: ACCENT }}>WHERE</span> status='paid'</div>
                            <div><span style={{ color: ACCENT }}>GROUP BY</span> region</div>
                            <div className="pt-3 mt-2 border-t border-white/[0.05] text-neutral-400">
                                ✓ The SQL you see is the SQL that ran — definition: <span className="text-neutral-300">net_revenue</span>
                            </div>
                            <div className="text-neutral-400">
                                ✓ Query, result, and audit entry stored alongside the answer
                            </div>
                        </div>
                    </ProofCard>
                </div>

                <div className="mt-14 text-center">
                    <p className="text-sm text-neutral-500 max-w-lg mx-auto leading-relaxed">
                        No invented logos, no placeholder quotes. When we have customers to brag about, we'll show you — with their permission, and their numbers.
                    </p>
                </div>
            </div>
        </section>
    );
};

export default ProofSection;
