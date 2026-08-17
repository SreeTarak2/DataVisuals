import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, Terminal, ShieldCheck, Plug, MessageSquareText } from 'lucide-react';
import SubPageLayout from '@/components/landing/SubPageLayout';

const ACCENT = '#F97316';

const DocSection = ({ id, icon, title, children }) => {
  const Icon = icon;
  return (
  <section id={id || title.toLowerCase().replace(/\s+/g, '-')} className="py-14 border-b border-white/[0.04] last:border-0">
    <div className="flex items-center gap-3 mb-6">
      <div className="w-9 h-9 rounded-lg border flex items-center justify-center" style={{ background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.22)', color: ACCENT }}>
        <Icon className="w-4 h-4" />
      </div>
      <h2 className="text-2xl font-bold text-white tracking-tight">{title}</h2>
    </div>
    <div className="space-y-4 max-w-3xl text-neutral-400 text-[15px] leading-relaxed">{children}</div>
  </section>
  );
};

const Code = ({ children }) => <div className="lp-code">{children}</div>;

const DocsPage = () => {
  return (
    <SubPageLayout>
      {/* Header */}
      <div className="lp-page-header">
        <div className="lp-wrapper">
          <div className="lp-crumbs">
            <Link to="/">Home</Link> <span>/</span> <span>Docs</span>
          </div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-4" style={{ color: ACCENT }}>Documentation</div>
          <h1 className="lp-title mb-5">Signal docs</h1>
          <p className="lp-subtitle">
            Everything you need to go from zero to your first insight — and understand what happens under the hood.
          </p>
        </div>
      </div>

      <div className="py-8">
        <div className="lp-wrapper">
          {/* Quick start */}
          <DocSection id="getting-started" icon={Terminal} title="Getting started">
            <p><strong className="text-white">1. Create a free account.</strong> Head to <Link to="/register" className="text-[#F97316]">/register</Link> and sign up — email or Google.</p>
            <p><strong className="text-white">2. Connect data.</strong> Upload a CSV/Excel file, import a Google Sheet, or connect a live database from the Connectors page.</p>
            <p><strong className="text-white">3. Ask anything.</strong> Open the AI chat and ask in plain English. Signal writes and runs the SQL, then charts the answer.</p>
            <p><strong className="text-white">4. Teach it once.</strong> Correct any answer. Your definitions are stored in the belief store and applied to future answers automatically.</p>
          </DocSection>

          {/* Concepts */}
          <DocSection id="how-answers-work" icon={MessageSquareText} title="How answers work">
            <p>Every answer is produced by a pipeline: your question is routed to the best model via OpenRouter, the resulting SQL runs against DuckDB, and the response is validated before it reaches you.</p>
            <p>Answers carry provenance — the metric definition used, the SQL executed, and the row counts. Expand "technical details" on any message to audit the work.</p>
          </DocSection>

          {/* Connectors */}
          <DocSection id="connectors" icon={Plug} title="Connectors">
            <p>Signal connects to Postgres, MySQL, MongoDB, Supabase, Google Sheets, and Excel — plus a growing dlt-powered catalog (Stripe, Zendesk, Shopify, QuickBooks, and more) for SaaS sources.</p>
            <p>Database credentials are encrypted at rest. Each connection supports scheduled re-extraction so dashboards stay fresh.</p>
          </DocSection>

          {/* Security */}
          <DocSection id="security" icon={ShieldCheck} title="Security & privacy">
            <ul className="list-disc pl-5 space-y-2">
              <li>PII detection and redaction on upload and re-processing</li>
              <li>Your data is never used to train public AI models</li>
              <li>Encrypted database credentials (Fernet)</li>
              <li>Per-user daily LLM budgets — predictable cost, no runaway bills</li>
              <li>Role-based permissions and audit logging for teams</li>
            </ul>
          </DocSection>

          {/* API */}
          <DocSection id="api" icon={BookOpen} title="API">
            <p>Signal exposes a REST + WebSocket API. When self-hosting, the OpenAPI reference is served at <span className="lp-mono text-neutral-300">/docs</span> (Swagger UI) on your backend instance.</p>
            <p>Key endpoints:</p>
            <Code>
              <span className="k">POST</span> /api/auth/register&nbsp;&nbsp;<span className="c"># create account</span><br />
              <span className="k">POST</span> /api/datasets/upload&nbsp;&nbsp;<span className="c"># upload CSV/XLSX</span><br />
              <span className="k">WS</span>&nbsp;&nbsp;&nbsp;/api/chat/ws&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="c"># streaming chat</span><br />
              <span className="k">GET</span>&nbsp;&nbsp;/api/databases&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="c"># list connectors</span><br />
              <span className="k">POST</span> /api/agentic/query&nbsp;&nbsp;&nbsp;<span className="c"># multi-agent analysis</span>
            </Code>
          </DocSection>

          {/* CTA */}
          <div className="py-14 text-center">
            <h2 className="text-2xl md:text-3xl font-bold text-white mb-3 tracking-tight">Ready to try it yourself?</h2>
            <p className="text-neutral-400 mb-8">It takes about 30 seconds to get your first answer.</p>
            <Link to="/register" className="lp-btn lp-btn-primary lp-btn-lg">
              Start free <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </div>
    </SubPageLayout>
  );
};

export default DocsPage;
