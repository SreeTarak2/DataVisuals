import React from 'react';
import { PricingTiers } from './PricingTiers';

const ACCENT = '#F97316';

const PricingSection = () => {
    return (
        <section id="pricing" className="py-32 relative bg-[#0A0A0A] border-y border-white/[0.03]">
            <div className="container mx-auto px-6 max-w-6xl relative z-10">
                <div className="text-center mb-20">
                    <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-5" style={{ color: ACCENT }}>Pricing</div>
                    <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6 text-white">
                        Free to start. Honest from day one.
                    </h2>
                    <p className="text-lg text-neutral-400 max-w-2xl mx-auto">
                        Start free today. Paid plans are in development — we'll tell you the price before we charge it.
                    </p>
                </div>

                <PricingTiers />

                <p className="text-center text-sm text-neutral-500 mt-14">
                    All plans include per-user daily budget caps — predictable spend, no surprise bills.
                </p>
            </div>
        </section>
    );
};

export default PricingSection;
