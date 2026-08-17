// Shared pricing tier data — single source of truth for the landing section
// and the /pricing page.
export const TIERS = [
  {
    name: 'Free',
    blurb: 'Everything you need to get real work done.',
    price: '$0',
    priceNote: '/mo',
    cta: 'Start free',
    ctaTo: '/register',
    featured: false,
    features: [
      'CSV, Excel & Google Sheets uploads',
      'AI chat with streaming answers',
      'Auto-generated dashboards & charts',
      'Insight engine & anomaly detection',
      'Your data is never used for training',
    ],
  },
  {
    name: 'Pro',
    blurb: 'For teams that live in their data stack.',
    price: 'Early access',
    priceNote: '',
    cta: 'Request early access',
    ctaTo: '/demo',
    featured: true,
    features: [
      'Everything in Free',
      'Live database connectors (Postgres, MySQL, MongoDB, Supabase)',
      'dlt-powered SaaS connectors (Stripe, Zendesk, Shopify…)',
      'SQL editor with history & sharing',
      'Belief store & team memory',
      'Scheduled reports & proactive alerts',
    ],
  },
  {
    name: 'Enterprise',
    blurb: 'Governance, scale, and a human to talk to.',
    price: 'Custom',
    priceNote: '',
    cta: 'Contact sales',
    ctaTo: '/demo',
    featured: false,
    features: [
      'Everything in Pro',
      'Role-based access & permissions',
      'Audit logs & PII redaction controls',
      'Dedicated success manager',
      'Self-hosted / private deployment options',
    ],
  },
];
