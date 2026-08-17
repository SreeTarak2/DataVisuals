import React from 'react';
import { Link } from 'react-router-dom';
import SubPageLayout from '@/components/landing/SubPageLayout';
import { PricingTiers } from '@/components/landing/PricingTiers';

const ACCENT = '#F97316';

const faqs = [
  {
    q: 'Is the free plan really free?',
    a: 'Yes. Create an account, upload data, and start asking questions. The free tier is a real product, not a demo — it includes daily usage budgets so costs stay predictable for us and for you.',
  },
  {
    q: 'Why is Pro "coming soon"?',
    a: 'We are still calibrating what belongs in paid plans. Rather than publish prices we are not ready to charge, we are taking early-access requests and will price honestly before we launch.',
  },
  {
    q: 'What happens to my data if I switch plans?',
    a: 'Nothing. Your datasets, dashboards, and belief store stay yours. Plan changes only affect limits, not access to your data.',
  },
  {
    q: 'Do you offer discounts for startups or nonprofits?',
    a: 'We want to. Tell us about your team via the demo form and we will work something out.',
  },
];

const PricingPage = () => {
  return (
    <SubPageLayout>
      {/* Header */}
      <div className="lp-page-header">
        <div className="lp-wrapper">
          <div className="lp-crumbs">
            <Link to="/">Home</Link> <span>/</span> <span>Pricing</span>
          </div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-4" style={{ color: ACCENT }}>Pricing</div>
          <h1 className="lp-title mb-5">Free to start. Honest from day one.</h1>
          <p className="lp-subtitle">
            The free plan is real and usable today. Paid plans are in development — we'll publish the price before we charge it.
          </p>
        </div>
      </div>

      {/* Tiers */}
      <section className="py-20">
        <div className="lp-wrapper">
          <PricingTiers />

          <p className="text-center text-sm text-neutral-500 mt-14">
            All plans include per-user daily budget caps — predictable spend, no surprise bills.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 border-t border-white/[0.03]">
        <div className="lp-wrapper max-w-3xl">
          <h2 className="text-2xl md:text-4xl font-bold text-white mb-10 tracking-tight">Pricing questions</h2>
          <div className="space-y-6">
            {faqs.map((item, i) => (
              <div key={i} className="border-b border-white/[0.05] pb-6">
                <h3 className="font-semibold text-white text-lg mb-2">{item.q}</h3>
                <p className="text-neutral-400 leading-relaxed text-sm">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </SubPageLayout>
  );
};

export default PricingPage;
