import React from 'react';
import { motion } from 'framer-motion';
import { Check, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { TIERS } from './pricingTiers';

const ACCENT = '#F97316';

const TierCard = ({ tier, index }) => {
  const { featured } = tier;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className={`relative rounded-[2rem] p-10 flex flex-col ${featured ? 'transform md:scale-105' : ''}`}
      style={
        featured
          ? { background: 'linear-gradient(#0D0D0F, #0D0D0F) padding-box, linear-gradient(135deg, #F97316, #EA580C) border-box', border: '2px solid transparent', boxShadow: '0 0 60px -12px rgba(249,115,22,0.35)' }
          : { background: '#0D0D0F', border: '1px solid rgba(255,255,255,0.06)' }
      }
    >
      {featured && (
        <div className="absolute top-6 right-8 flex items-center gap-1 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest text-white"
          style={{ background: ACCENT }}>
          <Sparkles className="w-3 h-3" /> Coming soon
        </div>
      )}
      <h3 className="text-xl font-bold mb-2 text-white">{tier.name}</h3>
      <p className="text-neutral-500 text-sm mb-8 leading-relaxed">{tier.blurb}</p>
      <div className="mb-8">
        <span className="text-4xl font-bold text-white">{tier.price}</span>
        {tier.priceNote && <span className="text-base font-normal text-neutral-500 ml-2">{tier.priceNote}</span>}
      </div>
      <Link to={tier.ctaTo} className="mb-10 block">
        <button
          className={`w-full py-4 rounded-2xl font-bold transition-all ${featured
            ? 'text-white hover:-translate-y-0.5'
            : 'bg-white/[0.03] hover:bg-white/[0.08] text-white border border-white/[0.05]'}`}
          style={featured ? { background: ACCENT, boxShadow: '0 8px 24px -8px rgba(249,115,22,0.5)' } : undefined}
        >
          {tier.cta}
        </button>
      </Link>
      <ul className="space-y-4 text-sm text-neutral-300 mt-auto">
        {tier.features.map((f, i) => (
          <li key={i} className="flex items-start gap-3">
            <Check className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: ACCENT }} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
};

export const PricingTiers = () => (
  <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto items-stretch">
    {TIERS.map((tier, i) => (
      <TierCard key={tier.name} tier={tier} index={i} />
    ))}
  </div>
);

export default PricingTiers;
