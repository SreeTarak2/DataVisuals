import React from 'react';

// Real infrastructure the product runs on (verified in READMEs) — not customers.
const stack = [
    "OpenRouter",
    "DuckDB",
    "MongoDB",
    "ChromaDB",
    "Polars",
    "FAISS"
];

const PoweredBy = () => {
    return (
        <section className="py-20 border-y border-white/[0.03] bg-transparent overflow-hidden">
            <div className="container mx-auto px-6">
                <p className="text-center text-neutral-600 text-[10px] font-bold mb-12 tracking-[0.2em] uppercase">
                    Powered by an open, modern stack
                </p>

                <div className="relative flex overflow-x-hidden lp-marquee">
                    <div className="lp-marquee-track opacity-40 hover:opacity-100 transition-opacity">
                        {[...stack, ...stack, ...stack, ...stack].map((name, index) => (
                            <div
                                key={index}
                                className="text-xl md:text-2xl font-black text-neutral-400 hover:text-white transition-all cursor-default whitespace-nowrap tracking-tighter"
                            >
                                {name}
                            </div>
                        ))}
                    </div>
                </div>

                <p className="text-center text-neutral-600 text-xs mt-10 max-w-xl mx-auto leading-relaxed">
                    DuckDB executes your queries · ChromaDB + FAISS store what your team has taught the system ·
                    OpenRouter routes each question to the best model for the job.
                </p>
            </div>
        </section>
    );
};

export default PoweredBy;
