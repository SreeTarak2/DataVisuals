import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, PenLine } from 'lucide-react';
import SubPageLayout from '@/components/landing/SubPageLayout';

const ACCENT = '#F97316';

const BlogPage = () => {
  return (
    <SubPageLayout>
      <div className="lp-page-header">
        <div className="lp-wrapper">
          <div className="lp-crumbs">
            <Link to="/">Home</Link> <span>/</span> <span>Blog</span>
          </div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-4" style={{ color: ACCENT }}>Blog</div>
          <h1 className="lp-title mb-5">The Signal Blog</h1>
          <p className="lp-subtitle">
            Notes on building context-aware AI analytics — accuracy benchmarks, semantic layers, and the
            difference between answering and being right.
          </p>
        </div>
      </div>

      <div className="py-16">
        <div className="lp-wrapper max-w-3xl">
          <div className="rounded-3xl border border-white/[0.06] bg-[#0D0D0F] p-12 text-center">
            <div className="w-14 h-14 mx-auto mb-6 rounded-2xl border flex items-center justify-center"
              style={{ background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.22)', color: ACCENT }}>
              <PenLine className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3 tracking-tight">First posts coming soon.</h2>
            <p className="text-neutral-400 max-w-md mx-auto mb-8 leading-relaxed">
              We're going to publish our own accuracy benchmarks, honest comparisons, and engineering notes.
              No fluff — the receipts.
            </p>
            <Link to="/register" className="lp-btn lp-btn-primary">
              Get early access <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </div>
    </SubPageLayout>
  );
};

export default BlogPage;
