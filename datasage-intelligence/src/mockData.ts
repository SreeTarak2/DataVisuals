import { ReportData } from './types';

export const mockReport: ReportData = {
  datasetName: "Q1 Global Sales Performance",
  reportId: "SR-2026-0042",
  storyHeadline: "Revenue is surging in EMEA, but a hidden churn risk is emerging among high-value enterprise clients.",
  executiveSummary: "Our overall performance is strong with a 12.5% YoY growth. However, the data reveals a significant divergence: while small business acquisition is at an all-time high (+18%), our top-tier enterprise segment is showing early signs of contraction due to a 22% increase in support ticket volume. Addressing this service bottleneck is critical for maintaining long-term stability.",
  dataQualityScore: 94,
  kpis: [
    { 
      label: "Total Revenue", 
      value: "$4.2M", 
      change: 12.5, 
      trend: 'up',
      description: "Net revenue across all regions and segments.",
      sparkline: Array.from({ length: 10 }, (_, i) => ({ x: i, y: 30 + Math.random() * 20 }))
    },
    { 
      label: "Active Users", 
      value: "84.2k", 
      change: 8.2, 
      trend: 'up',
      description: "Monthly active users with at least one session.",
      sparkline: Array.from({ length: 10 }, (_, i) => ({ x: i, y: 50 + Math.random() * 10 }))
    },
    { 
      label: "Churn Rate", 
      value: "2.4%", 
      change: -0.5, 
      trend: 'down',
      description: "Percentage of customers who canceled their subscription.",
      sparkline: Array.from({ length: 10 }, (_, i) => ({ x: i, y: 10 - Math.random() * 5 }))
    },
    { 
      label: "Avg. Response Time", 
      value: "1.2h", 
      change: 15.0, 
      trend: 'up',
      description: "Time from ticket creation to first human response.",
      sparkline: Array.from({ length: 10 }, (_, i) => ({ x: i, y: 20 + Math.random() * 30 }))
    },
  ],
  recommendations: [
    { 
      id: '1', 
      text: "Increase support headcount for the Enterprise Tier immediately.", 
      impact: 'high', 
      category: 'Operations',
      rationale: "Correlation analysis shows a direct link between response times exceeding 2 hours and a 15% drop in renewal probability."
    },
    { 
      id: '2', 
      text: "Double down on the 'North Region' SMB marketing campaign.", 
      impact: 'medium', 
      category: 'Marketing',
      rationale: "The North Region SMB segment has a 40% higher LTV/CAC ratio compared to the global average."
    },
    { 
      id: '3', 
      text: "Investigate feature usage vs. churn in APAC.", 
      impact: 'medium', 
      category: 'Product',
      rationale: "Preliminary data suggests that users who don't adopt the 'Advanced Analytics' feature within 30 days are 3x more likely to churn."
    }
  ],
  sections: [
    {
      id: 's1',
      title: "Regional Performance Divergence",
      narrative: "While the global trend is positive, we are seeing a widening gap between EMEA and other regions. EMEA's growth is primarily driven by the 'Cloud-First' initiative, which has seen a 45% adoption rate among existing customers.",
      insights: [
        {
          id: 'i1',
          type: 'trend',
          title: "EMEA Revenue Momentum",
          description: "EMEA revenue has consistently outperformed projections for 3 consecutive months, driven primarily by the new 'Cloud-First' initiative.",
          value: "+24.5%",
          severity: 'positive',
          tags: ['EMEA', 'Revenue', 'Cloud'],
          data: [
            { name: 'Jan', value: 400 },
            { name: 'Feb', value: 450 },
            { name: 'Mar', value: 520 },
          ],
          analyticalContext: {
            pValue: 0.001,
            sampleSize: 1240,
            confidenceInterval: [22.1, 26.9],
            methodology: "Time-series regression analysis",
            lastUpdated: "2026-03-09T04:00:00Z",
            dataOrigin: "Salesforce CRM + Snowflake Data Warehouse"
          }
        }
      ]
    },
    {
      id: 's2',
      title: "Enterprise Segment Risk Analysis",
      narrative: "The Enterprise segment, which accounts for 65% of our total revenue, is showing signs of instability. The primary driver appears to be service latency, which has reached a critical threshold for our top 100 accounts.",
      insights: [
        {
          id: 'i2',
          type: 'anomaly',
          title: "Enterprise Churn Anomaly",
          description: "We've detected an unexpected spike in cancellation requests from clients with >$50k ARR. This deviates from the 2-year seasonal norm.",
          value: "22% Spike",
          severity: 'critical',
          tags: ['Enterprise', 'Churn', 'Risk'],
          analyticalContext: {
            pValue: 0.042,
            sampleSize: 150,
            methodology: "Z-score outlier detection",
            lastUpdated: "2026-03-09T04:05:00Z",
            dataOrigin: "Zendesk Support + Stripe Billing"
          }
        },
        {
          id: 'i4',
          type: 'correlation',
          title: "Support Latency vs. Renewal",
          description: "We found a strong inverse correlation between first-response time and contract renewal rates in the Enterprise segment.",
          severity: 'neutral',
          tags: ['Support', 'Retention', 'Correlation'],
          data: [
            { x: 10, y: 90 },
            { x: 20, y: 75 },
            { x: 30, y: 60 },
            { x: 40, y: 40 },
            { x: 50, y: 20 },
          ],
          analyticalContext: {
            pValue: 0.005,
            sampleSize: 800,
            confidenceInterval: [-0.85, -0.65],
            methodology: "Pearson correlation coefficient",
            lastUpdated: "2026-03-09T04:10:00Z",
            dataOrigin: "Zendesk + Salesforce"
          }
        }
      ]
    }
  ]
};
