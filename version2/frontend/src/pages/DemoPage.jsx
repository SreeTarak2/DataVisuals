import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CalendarCheck, Mail, CheckCircle2 } from 'lucide-react';
import SubPageLayout from '@/components/landing/SubPageLayout';

const ACCENT = '#F97316';

// TODO(launch): replace with the real demo inbox (or wire to a form service like
// Formspree/Resend). The mailto flow is a zero-backend placeholder until then.
const DEMO_EMAIL = 'hello@signal-analytics.example';

const initialForm = {
  name: '',
  email: '',
  company: '',
  role: '',
  dataStack: '',
  message: '',
};

const DemoPage = () => {
  const [form, setForm] = useState(initialForm);
  const [sent, setSent] = useState(false);

  const update = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const subject = encodeURIComponent(`Demo request — ${form.company || form.name}`);
    const body = encodeURIComponent(
      `Name: ${form.name}\nEmail: ${form.email}\nCompany: ${form.company}\nRole: ${form.role}\nData stack: ${form.dataStack}\n\nQuestions:\n${form.message}`
    );
    window.location.href = `mailto:${DEMO_EMAIL}?subject=${subject}&body=${body}`;
    setSent(true);
  };

  return (
    <SubPageLayout>
      <div className="lp-page-header">
        <div className="lp-wrapper">
          <div className="lp-crumbs">
            <Link to="/">Home</Link> <span>/</span> <span>Book a demo</span>
          </div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-4" style={{ color: ACCENT }}>Book a demo</div>
          <h1 className="lp-title mb-5">See Signal with your data.</h1>
          <p className="lp-subtitle">
            Tell us about your team and your data stack. We'll show you Signal against your own use cases — dashboards,
            queries, and the learning loop included.
          </p>
        </div>
      </div>

      <div className="py-16">
        <div className="lp-wrapper max-w-6xl">
          <div className="grid md:grid-cols-2 gap-12 items-start">
            {/* Form */}
            <div className="lp-card p-8 md:p-10">
              {sent ? (
                <div className="text-center py-10">
                  <CheckCircle2 className="w-12 h-12 mx-auto mb-6" style={{ color: ACCENT }} />
                  <h2 className="text-xl font-bold text-white mb-3">Request prepared!</h2>
                  <p className="text-neutral-400 leading-relaxed mb-6">
                    Your email app should have opened with the request pre-filled. If it didn't, email us directly at{' '}
                    <span className="lp-mono text-neutral-300">{DEMO_EMAIL}</span>.
                  </p>
                  <button onClick={() => setSent(false)} className="lp-btn lp-btn-outline">Edit request</button>
                </div>
              ) : (
                <form className="lp-form" onSubmit={handleSubmit}>
                  <div className="grid sm:grid-cols-2 gap-5">
                    <div className="lp-field">
                      <label htmlFor="demo-name">Name</label>
                      <input id="demo-name" required value={form.name} onChange={update('name')} placeholder="Jane Smith" />
                    </div>
                    <div className="lp-field">
                      <label htmlFor="demo-email">Work email</label>
                      <input id="demo-email" type="email" required value={form.email} onChange={update('email')} placeholder="jane@company.com" />
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-5">
                    <div className="lp-field">
                      <label htmlFor="demo-company">Company</label>
                      <input id="demo-company" value={form.company} onChange={update('company')} placeholder="Acme, Inc." />
                    </div>
                    <div className="lp-field">
                      <label htmlFor="demo-role">Your role</label>
                      <input id="demo-role" value={form.role} onChange={update('role')} placeholder="Head of BI" />
                    </div>
                  </div>
                  <div className="lp-field">
                    <label htmlFor="demo-stack">Data stack</label>
                    <input id="demo-stack" value={form.dataStack} onChange={update('dataStack')} placeholder="Postgres, Google Sheets, CSVs…" />
                  </div>
                  <div className="lp-field">
                    <label htmlFor="demo-message">What would you like to see?</label>
                    <textarea id="demo-message" value={form.message} onChange={update('message')} placeholder="We're most interested in…" />
                  </div>
                  <button type="submit" className="lp-btn lp-btn-primary lp-btn-lg w-full">
                    <Mail size={16} /> Send demo request
                  </button>
                  <p className="text-xs text-neutral-500 text-center">
                    Opens a pre-filled email to {DEMO_EMAIL}. (This demo inbox is a placeholder until the real one is connected.)
                  </p>
                </form>
              )}
            </div>

            {/* Why book */}
            <div className="space-y-6">
              <div className="lp-card p-8">
                <div className="lp-icon-tile mb-4"><CalendarCheck className="w-5 h-5" /></div>
                <h3 className="text-lg font-bold text-white mb-2">What the demo covers</h3>
                <ul className="space-y-3 text-sm text-neutral-400">
                  <li className="flex gap-2"><span style={{ color: ACCENT }}>›</span> Connecting your database or uploading your data</li>
                  <li className="flex gap-2"><span style={{ color: ACCENT }}>›</span> Asking questions and watching the SQL + chart stream in</li>
                  <li className="flex gap-2"><span style={{ color: ACCENT }}>›</span> The learning loop — correcting an answer once, seeing it stick</li>
                  <li className="flex gap-2"><span style={{ color: ACCENT }}>›</span> Dashboards, reports, and team governance</li>
                </ul>
              </div>

              <div className="lp-card p-8">
                <div className="lp-icon-tile mb-4"><ArrowRight className="w-5 h-5" /></div>
                <h3 className="text-lg font-bold text-white mb-2">Prefer to just try it?</h3>
                <p className="text-sm text-neutral-400 mb-5 leading-relaxed">
                  The free plan is the real product. No demo required.
                </p>
                <Link to="/register" className="lp-btn lp-btn-primary w-full">
                  Start free now <ArrowRight size={16} />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </SubPageLayout>
  );
};

export default DemoPage;
