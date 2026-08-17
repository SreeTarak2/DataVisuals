import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

const ACCENT = '#F97316';

const faqs = [
    {
        question: "What data sources can I connect?",
        answer: "Upload CSV, Excel, or import a Google Sheet. Or connect live databases — Postgres, MySQL, MongoDB, Supabase, and Google Sheets — with more connectors (including dlt-powered sources like Stripe, Zendesk, and Shopify) in the pipeline.",
    },
    {
        question: "Do I need to know SQL or Python?",
        answer: "No. You ask questions in plain English and Signal writes the SQL. That said, analysts who want to see, edit, or reuse the SQL get a full SQL editor with history, sharing, and export.",
    },
    {
        question: "How does Signal get more accurate over time?",
        answer: "Every correction you make is stored in a belief store — your metric definitions, terminology, and preferences. Future answers use that context automatically, so the system compounds what your team knows instead of forgetting it between sessions.",
    },
    {
        question: "How do I know the answers are right?",
        answer: "Every answer shows its work: the metric definition used, the SQL that produced it, and the row counts behind it. Deterministic KPIs and confidence intervals are computed from your data — not guessed by the model.",
    },
    {
        question: "Is my data secure?",
        answer: "Yes. We detect and redact PII, encrypt database credentials at rest, and your data is never used to train public models. Role-based access and audit logging are available for teams.",
    },
    {
        question: "What AI models power the answers?",
        answer: "Signal routes each question to the best model for the job via OpenRouter — from lightweight streaming models for chat to deep-reasoning models for complex analysis — with per-user daily budgets so costs stay predictable.",
    },
];

const FAQSection = () => {
    const [openIndex, setOpenIndex] = useState(0);

    return (
        <section id="faq" className="py-24 relative">
            <div className="container mx-auto px-6 max-w-3xl relative z-10">
                <div className="text-center mb-16">
                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5" style={{ color: ACCENT }}>FAQ</div>
                    <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white">
                        Frequently Asked Questions
                    </h2>
                </div>

                <div className="space-y-4">
                    {faqs.map((faq, index) => {
                        const isOpen = openIndex === index;
                        return (
                            <div key={index} className="border-b border-white/[0.05] pb-4">
                                <button
                                    className="flex justify-between items-center w-full text-left py-6 focus:outline-none group"
                                    onClick={() => setOpenIndex(isOpen ? null : index)}
                                    aria-expanded={isOpen}
                                >
                                    <span className="font-medium text-lg transition-colors" style={{ color: isOpen ? ACCENT : '#FFFFFF' }}>
                                        {faq.question}
                                    </span>
                                    <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                                        <ChevronDown className="w-5 h-5 transition-colors" style={{ color: isOpen ? ACCENT : '#737373' }} />
                                    </motion.div>
                                </button>
                                <AnimatePresence>
                                    {isOpen && (
                                        <motion.div
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: 'auto', opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            transition={{ duration: 0.3, ease: "easeInOut" }}
                                            className="overflow-hidden"
                                        >
                                            <p className="text-neutral-400 pb-8 pr-12 leading-relaxed">{faq.answer}</p>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};

export default FAQSection;
