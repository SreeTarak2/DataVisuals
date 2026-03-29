import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

const faqs = [
    {
        question: "What types of files can I upload?",
        answer: "Currently, DataSage supports CSV, and Excel (XLSX, XLS) files up to 50MB."
    },
    {
        question: "Is my data secure?",
        answer: "Yes, your data is processed securely and is never used to train public AI models. We use encryption at rest and in transit."
    },
    {
        question: "Do I need to know SQL or Python?",
        answer: "Not at all. DataSage uses natural language processing. You just ask questions in plain English, and our AI generates the insights and charts."
    }
];

const FAQSection = () => {
    const [openIndex, setOpenIndex] = useState(null);

    return (
        <section id="faq" className="py-24 relative">
            <div className="container mx-auto px-6 max-w-3xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        Frequently Asked Questions
                    </motion.h2>
                </div>

                <div className="space-y-4">
                    {faqs.map((faq, index) => (
                        <div key={index} className="border-b border-white/[0.05] pb-4">
                            <button
                                className="flex justify-between items-center w-full text-left py-6 focus:outline-none group"
                                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                            >
                                <span className={`font-medium text-lg transition-colors ${openIndex === index ? 'text-blue-400' : 'text-white'}`}>{faq.question}</span>
                                <motion.div
                                    animate={{ rotate: openIndex === index ? 180 : 0 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <ChevronDown className={`w-5 h-5 transition-colors ${openIndex === index ? 'text-blue-400' : 'text-neutral-500'}`} />
                                </motion.div>
                            </button>
                            <AnimatePresence>
                                {openIndex === index && (
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
                    ))}
                </div>
            </div>
        </section>
    );
};

export default FAQSection;
