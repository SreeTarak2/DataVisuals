
export type InsightType = 'anomaly' | 'trend' | 'correlation' | 'segment';

export interface Recommendation {
  id: string;
  text: string;
  impact: 'high' | 'medium' | 'low';
  category: string;
  rationale: string;
}

export interface AnalyticalContext {
  pValue?: number;
  sampleSize?: number;
  confidenceInterval?: [number, number];
  methodology?: string;
  lastUpdated: string;
  dataOrigin: string;
}

export interface Insight {
  id: string;
  type: InsightType;
  title: string;
  description: string;
  value?: string | number;
  change?: number;
  data?: any[];
  severity: 'critical' | 'positive' | 'neutral';
  analyticalContext?: AnalyticalContext;
  tags: string[];
}

export interface KPI {
  label: string;
  value: string;
  change: number;
  trend: 'up' | 'down' | 'neutral';
  sparkline: { x: number; y: number }[];
  description: string;
}

export interface ReportSection {
  id: string;
  title: string;
  narrative: string;
  insights: Insight[];
}

export interface ReportData {
  datasetName: string;
  reportId: string;
  storyHeadline: string;
  executiveSummary: string;
  dataQualityScore: number;
  kpis: KPI[];
  recommendations: Recommendation[];
  sections: ReportSection[];
}
