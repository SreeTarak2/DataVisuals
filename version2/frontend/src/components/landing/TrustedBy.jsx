import React from 'react';

const TrustedBy = () => {
    const partners = [
        "OpenRouter",
        "Mistral AI",
        "Meta Llama",
        "Qwen",
        "LangChain"
    ];

    return (
        <section className="py-12 border-y border-white/5 bg-slate-950 overflow-hidden">
            <div className="container mx-auto px-6">
                <p className="text-center text-slate-500 text-xs font-semibold mb-8 tracking-widest uppercase">
                    Powered by world-class infrastructure
                </p>

                {/* Auto-scrolling carousel setup */}
                <div className="relative flex overflow-x-hidden">
                    <div className="animate-marquee whitespace-nowrap flex items-center gap-16 md:gap-32 py-4">
                        {[...partners, ...partners, ...partners].map((partner, index) => (
                            <div
                                key={index}
                                className="text-xl md:text-2xl font-bold text-slate-700/80 hover:text-slate-400 transition-colors cursor-default whitespace-nowrap"
                            >
                                {partner}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
};

export default TrustedBy;
