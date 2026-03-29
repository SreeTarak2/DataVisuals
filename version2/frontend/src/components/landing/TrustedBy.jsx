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
        <section className="py-20 border-y border-white/[0.03] bg-transparent overflow-hidden">
            <div className="container mx-auto px-6">
                <p className="text-center text-neutral-600 text-[10px] font-bold mb-12 tracking-[0.2em] uppercase">
                    Unlocking insights for the modern era
                </p>

                <div className="relative flex overflow-x-hidden">
                    <div className="animate-marquee whitespace-nowrap flex items-center gap-24 md:gap-40 py-4 opacity-40 hover:opacity-100 transition-opacity">
                        {[...partners, ...partners, ...partners].map((partner, index) => (
                            <div
                                key={index}
                                className="text-xl md:text-2xl font-black text-neutral-400 hover:text-white transition-all cursor-default whitespace-nowrap tracking-tighter"
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
