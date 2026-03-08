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
        <section className="py-12 bg-[#020617] border-y border-slate-900">
            <div className="container mx-auto px-6">
                <p className="text-center text-slate-500 text-xs font-semibold mb-8 tracking-widest uppercase">
                    Powered by world-class infrastructure
                </p>
                <div className="flex flex-wrap justify-center items-center gap-10 md:gap-20">
                    {partners.map((partner, index) => (
                        <div
                            key={index}
                            className="text-lg md:text-xl font-bold text-slate-600 hover:text-slate-300 transition-colors cursor-default"
                        >
                            {partner}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};

export default TrustedBy;
