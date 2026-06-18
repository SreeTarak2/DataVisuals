import React, { useState, useRef, useCallback, useMemo } from 'react'
import EnterpriseKpiCard from '../../components/ui/EnterpriseKpiCard'
import { Skeleton } from '../../components/ui/skeleton'

const DEFAULT_KPIS = []

const SAMPLE_JSON = `[
  {
    "type": "kpi",
    "column": "revenue",
    "importance": "hero",
    "title": "Total Revenue",
    "value": 2000000.0,
    "format": "currency",
    "delta_percent": 35.8,
    "delta_direction": "up",
    "is_delta_positive": true,
    "business_category": "revenue",
    "archetype": "saas",
    "sparkline_data": { "data": [120000, 135000, 128000, 142000, 158000, 165000, 172000, 180000, 175000, 190000, 210000, 225000], "type": "time_series" },
    "ai_suggestion": "Total Revenue grew 35.8% over the period, driven primarily by strong Q4 performance.",
    "action_prompt": "Break down Total Revenue by region.",
    "comparison_value": 848000,
    "comparison_label": "vs first half",
    "benchmark_value": 180000,
    "benchmark_text": "Top 25%: $180.0K",
    "trend_direction": "up",
    "is_anomaly": false,
    "anomaly_severity": "normal",
    "top_driver": { "dimension": "churned_users", "segment": "28", "pct_of_total": 18.8 }
  },
  {
    "type": "kpi",
    "column": "cost",
    "importance": "high",
    "title": "Total Cost",
    "value": 648000,
    "format": "currency",
    "delta_percent": 19.7,
    "delta_direction": "up",
    "is_delta_positive": false,
    "business_category": "cost",
    "sparkline_data": { "data": [45000, 48000, 47000, 49000, 52000, 54000, 55000, 57000, 56000, 58000, 62000, 65000], "type": "time_series" },
    "ai_suggestion": "Total Cost increased 19.7%, growing slower than revenue.",
    "comparison_value": 291000,
    "trend_direction": "up",
    "is_anomaly": true,
    "anomaly_severity": "medium",
    "anomaly_direction": "above_normal",
    "z_score": 2.1
  },
  {
    "type": "kpi",
    "column": "users",
    "importance": "high",
    "title": "Average Users",
    "value": 1910,
    "format": "integer",
    "delta_percent": 31.6,
    "delta_direction": "up",
    "is_delta_positive": true,
    "business_category": "users",
    "sparkline_data": { "data": [1500, 1620, 1580, 1720, 1850, 1950, 2050, 2120, 2080, 2200, 2400, 2600], "type": "time_series" },
    "ai_suggestion": "User base grew 31.6% with accelerating growth in H2.",
    "trend_direction": "up"
  },
  {
    "type": "kpi",
    "column": "mrr",
    "importance": "high",
    "title": "Average MRR",
    "value": 171917,
    "format": "currency",
    "delta_percent": 35.2,
    "delta_direction": "up",
    "is_delta_positive": true,
    "business_category": "revenue",
    "sparkline_data": { "data": [125000, 140000, 132000, 148000, 162000, 170000, 178000, 186000, 181000, 196000, 215000, 230000], "type": "time_series" },
    "ai_suggestion": "MRR grew consistently throughout the year.",
    "trend_direction": "up",
    "comparison_value": 430000,
    "comparison_label": "vs first half"
  }
]`

function normalizeKpi(entry) {
  if (entry.type !== 'kpi') return null
  return {
    ...entry,
    comparisonValue: entry.comparisonValue ?? entry.comparison_value ?? null,
    comparisonLabel: entry.comparisonLabel ?? entry.comparison_label ?? null,
    deltaPercent: entry.deltaPercent ?? entry.delta_percent ?? null,
    benchmarkValue: entry.benchmarkValue ?? entry.benchmark_value ?? null,
    benchmarkLabel: entry.benchmarkLabel ?? entry.benchmark_label ?? null,
    benchmarkText: entry.benchmarkText ?? entry.benchmark_text ?? null,
    aiSuggestion: entry.aiSuggestion ?? entry.ai_suggestion ?? null,
    actionPrompt: entry.actionPrompt ?? entry.action_prompt ?? null,
    businessCategory: entry.businessCategory ?? entry.business_category ?? null,
    periodLabel: entry.periodLabel ?? entry.period_label ?? null,
    previousPeriodLabel: entry.previousPeriodLabel ?? entry.previous_period_label ?? null,
    periodType: entry.periodType ?? entry.period_type ?? null,
    baselineValue: entry.baselineValue ?? entry.baseline_value ?? null,
    baselineLabel: entry.baselineLabel ?? entry.baseline_label ?? null,
    vsBaselinePct: entry.vsBaselinePct ?? entry.vs_baseline_pct ?? null,
    baselineStd: entry.baselineStd ?? entry.baseline_std ?? null,
    normalRangeLow: entry.normalRangeLow ?? entry.normal_range_low ?? null,
    normalRangeHigh: entry.normalRangeHigh ?? entry.normal_range_high ?? null,
    isAnomaly: entry.isAnomaly ?? entry.is_anomaly ?? false,
    anomalyDirection: entry.anomalyDirection ?? entry.anomaly_direction ?? null,
    zScore: entry.zScore ?? entry.z_score ?? 0,
    anomalySeverity: entry.anomalySeverity ?? entry.anomaly_severity ?? 'normal',
    expectedValue: entry.expectedValue ?? entry.expected_value ?? null,
    trendDirection: entry.trendDirection ?? entry.trend_direction ?? 'flat',
    topDriver: entry.topDriver ?? entry.top_driver ?? null,
    vsPreviousPct: entry.vsPreviousPct ?? entry.vs_previous_pct ?? null,
    recordCount: entry.recordCount ?? entry.record_count ?? null,
    accentColor: entry.accentColor ?? entry.accent_color ?? null,
    sparklineData: entry.sparklineData ?? entry.sparkline_data ?? [],
    staleMinutes: entry.staleMinutes ?? entry.stale_minutes ?? null,
  }
}

const CARD_GRID = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 md:grid-cols-2',
  3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
}

function KpiTest() {
  const [kpiData, setKpiData] = useState(DEFAULT_KPIS)
  const [forcedState, setForcedState] = useState('ready')
  const [gridCols, setGridCols] = useState(3)
  const [compact, setCompact] = useState(false)
  const [showRaw, setShowRaw] = useState(false)
  const [jsonInput, setJsonInput] = useState('')
  const fileRef = useRef(null)

  const selectedState = forcedState === 'ready' || kpiData.length === 0 && forcedState === 'ready' ? 'ready' : forcedState

  const handleFile = useCallback((e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        const items = Array.isArray(data) ? data : data.kpis ?? data.components ?? []
        setKpiData(items)
        setJsonInput(JSON.stringify(items, null, 2))
        setForcedState('ready')
      } catch (err) {
        alert('Invalid JSON: ' + err.message)
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }, [])

  const handlePaste = useCallback(() => {
    try {
      const data = JSON.parse(jsonInput)
      const items = Array.isArray(data) ? data : data.kpis ?? data.components ?? []
      setKpiData(items)
      setForcedState('ready')
    } catch (err) {
      alert('Invalid JSON: ' + err.message)
    }
  }, [jsonInput])

  const loadSample = useCallback(() => {
    setJsonInput(SAMPLE_JSON)
    try {
      const data = JSON.parse(SAMPLE_JSON)
      setKpiData(data)
      setForcedState('ready')
    } catch {
      // sample JSON is valid — no error handling needed
    }
  }, [])

  const clearCards = useCallback(() => {
    setKpiData([])
    setJsonInput('')
  }, [])

  const normalizedKpis = useMemo(() => {
    return kpiData.map(normalizeKpi).filter(Boolean)
  }, [kpiData])

  return (
    <div className={compact ? '' : 'min-h-screen'} style={{ background: '#0a0a0f' }}>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-semibold text-white/90">KPI Card Test Harness</h1>
            <p className="text-xs text-white/40 mt-0.5">
              {normalizedKpis.length} card{normalizedKpis.length !== 1 ? 's' : ''} loaded
              {' · '}state: <span className="text-white/60 font-mono">{selectedState}</span>
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 mb-4 p-3 rounded-lg bg-white/5 border border-white/10">
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            onChange={handleFile}
            className="text-xs text-white/60 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-white/10 file:text-white/80 hover:file:bg-white/15 cursor-pointer"
          />
          <button onClick={loadSample} className="px-3 py-1 text-xs font-medium rounded bg-white/10 text-white/80 hover:bg-white/15">
            Sample
          </button>
          <button onClick={clearCards} className="px-3 py-1 text-xs font-medium rounded bg-white/5 text-white/50 hover:bg-white/10">
            Clear
          </button>

          <span className="w-px h-5 bg-white/10 mx-1" />

          {['ready', 'loading', 'empty', 'error'].map((s) => (
            <button
              key={s}
              onClick={() => setForcedState(s)}
              className={`px-2.5 py-1 text-xs rounded font-medium transition ${
                forcedState === s
                  ? 'bg-white/20 text-white'
                  : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70'
              }`}
            >
              {s}
            </button>
          ))}

          <span className="w-px h-5 bg-white/10 mx-1" />

          {[1, 2, 3, 4].map((n) => (
            <button
              key={n}
              onClick={() => setGridCols(n)}
              className={`px-2 py-1 text-xs rounded font-medium transition ${
                gridCols === n
                  ? 'bg-white/20 text-white'
                  : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70'
              }`}
            >
              {n}×{n === 1 ? '1' : n === 2 ? '2' : n === 3 ? '3' : '4'}
            </button>
          ))}

          <label className="flex items-center gap-1.5 text-xs text-white/50 cursor-pointer ml-1">
            <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} className="accent-white/50" />
            Compact
          </label>

          <button
            onClick={() => setShowRaw((v) => !v)}
            className={`px-2.5 py-1 text-xs rounded font-medium transition ml-auto ${
              showRaw ? 'bg-white/20 text-white' : 'bg-white/5 text-white/50 hover:bg-white/10'
            }`}
          >
            {showRaw ? 'Hide JSON' : 'Raw JSON'}
          </button>
        </div>

        {/* JSON input area */}
        <div className="flex gap-2 mb-4">
          <textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            placeholder="Paste KPI JSON here, then click Load..."
            rows={4}
            className="flex-1 text-xs font-mono text-white/60 bg-white/5 border border-white/10 rounded p-2 resize-none placeholder:text-white/20"
          />
          <button
            onClick={handlePaste}
            className="px-4 py-2 text-xs font-medium rounded bg-white/10 text-white/80 hover:bg-white/15 self-end"
          >
            Load
          </button>
        </div>

        {/* KPI Card Grid */}
        {normalizedKpis.length > 0 ? (
          <div className={`grid ${CARD_GRID[gridCols]} gap-3`}>
            {normalizedKpis.map((kpi, idx) => (
              <EnterpriseKpiCard
                key={kpi.column ?? kpi.title ?? idx}
                title={kpi.title}
                value={kpi.value ?? 0}
                format={kpi.format || 'number'}
                definition={kpi.definition ?? kpi.subtitle ?? null}
                comparisonValue={kpi.comparisonValue ?? null}
                comparisonLabel={kpi.comparisonLabel ?? null}
                deltaPercent={kpi.deltaPercent ?? null}
                benchmarkValue={kpi.benchmarkValue ?? null}
                benchmarkLabel={kpi.benchmarkLabel ?? null}
                benchmarkText={kpi.benchmarkText ?? null}
                isOutlier={kpi.isOutlier ?? false}
                aiSuggestion={kpi.aiSuggestion ?? null}
                actionPrompt={kpi.actionPrompt ?? null}
                sparklineData={kpi.sparklineData ?? []}
                recordCount={kpi.recordCount ?? null}
                icon={kpi.icon || 'BarChart3'}
                state={selectedState}
                accentColor={kpi.accentColor ?? null}
                businessCategory={kpi.businessCategory ?? null}
                periodLabel={kpi.periodLabel ?? null}
                previousPeriodLabel={kpi.previousPeriodLabel ?? null}
                periodType={kpi.periodType ?? null}
                baselineValue={kpi.baselineValue ?? null}
                baselineLabel={kpi.baselineLabel ?? null}
                vsBaselinePct={kpi.vsBaselinePct ?? null}
                baselineStd={kpi.baselineStd ?? null}
                normalRangeLow={kpi.normalRangeLow ?? null}
                normalRangeHigh={kpi.normalRangeHigh ?? null}
                isAnomaly={kpi.isAnomaly ?? false}
                anomalyDirection={kpi.anomalyDirection ?? null}
                zScore={kpi.zScore ?? 0}
                anomalySeverity={kpi.anomalySeverity ?? 'normal'}
                expectedValue={kpi.expectedValue ?? null}
                trendDirection={kpi.trendDirection ?? 'flat'}
                topDriver={kpi.topDriver ?? null}
                vsPreviousPct={kpi.vsPreviousPct ?? null}
                staleMinutes={kpi.staleMinutes ?? null}
                compact={compact}
                theme="dark"
              />
            ))}
          </div>
        ) : selectedState === 'loading' ? (
          <div className={`grid ${CARD_GRID[gridCols]} gap-3`}>
            {Array.from({ length: gridCols }).map((_, i) => (
              <div key={i} className="flex flex-col gap-4 p-5 rounded-xl border border-white/10 bg-white/5">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-3 w-32 rounded" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <div className="space-y-2">
                  <Skeleton className="h-9 w-36 rounded" />
                  <Skeleton className="h-3 w-20 rounded" />
                </div>
                <Skeleton className="h-10 w-full rounded" />
                <div className="grid grid-cols-3 gap-2">
                  <Skeleton className="h-12 rounded-lg" />
                  <Skeleton className="h-12 rounded-lg" />
                  <Skeleton className="h-12 rounded-lg" />
                </div>
                <Skeleton className="h-16 w-full rounded-lg" />
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-white/30">
            <p className="text-sm">Load KPI JSON to see rendered cards</p>
            <p className="text-xs mt-1">Run the backend pipeline and feed the output here</p>
          </div>
        )}

        {/* Raw JSON */}
        {showRaw && normalizedKpis.length > 0 && (
          <details open className="mt-6">
            <summary className="text-xs text-white/40 cursor-pointer mb-2 hover:text-white/60">
              Raw KPI JSON ({normalizedKpis.length} cards)
            </summary>
            <pre className="text-xs text-white/40 font-mono bg-white/5 border border-white/10 rounded p-3 max-h-96 overflow-auto whitespace-pre-wrap">
              {JSON.stringify(normalizedKpis, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  )
}

export default KpiTest
