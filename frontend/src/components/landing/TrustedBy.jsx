import React from 'react';

const TrustedBy = () => {
    // Ideally use real SVGs, for now using text/placeholders styled to look like logos
    const partners = [
        { name: "OpenRouter", opacity: "opacity-80" },
        { name: "Mistral AI", opacity: "opacity-70" },
        { name: "Meta Llama", opacity: "opacity-75" },
        { name: "Qwen", opacity: "opacity-70" },
        { name: "LangChain", opacity: "opacity-60" }
    ];

    return (
        <section className="py-10 bg-slate-950 border-b border-white/5">
            <div className="container mx-auto px-4">
                <p className="text-center text-slate-500 text-sm font-semibold mb-6 tracking-wide uppercase">Powered by World-Class AI Models</p>
                <div className="flex flex-wrap justify-center items-center gap-8 md:gap-16 grayscale">
                    {partners.map((partner, index) => (
                        <div key={index} className={`text-xl md:text-2xl font-bold text-slate-400 ${partner.opacity} hover:opacity-100 hover:text-white transition-all cursor-default`}>
                            {partner.name}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};

export default TrustedBy;
