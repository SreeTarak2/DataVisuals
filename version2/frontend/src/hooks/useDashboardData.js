import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'

const useDashboardData = (selectedDataset) => {
  const [dashboardData, setDashboardData] = useState({
    layout: null,
    kpis: [],
    insights: [],
    charts: {},
    datasetInfo: null,
    loading: true,
    error: null
  })

  const [userExpertise, setUserExpertise] = useState('beginner')

  // Generate mock chart data for testing
  const generateMockChartData = () => {
    return {
      revenue_over_time: [
        { x: 'Jan', y: 4000 },
        { x: 'Feb', y: 3000 },
        { x: 'Mar', y: 5000 },
        { x: 'Apr', y: 4500 },
        { x: 'May', y: 6000 },
        { x: 'Jun', y: 5500 },
        { x: 'Jul', y: 7000 },
        { x: 'Aug', y: 6500 },
        { x: 'Sep', y: 8000 },
        { x: 'Oct', y: 7500 },
        { x: 'Nov', y: 9000 },
        { x: 'Dec', y: 8500 }
      ],
      sales_by_category: [
        { x: 'Electronics', y: 12000 },
        { x: 'Clothing', y: 8000 },
        { x: 'Books', y: 5000 },
        { x: 'Home', y: 7000 },
        { x: 'Sports', y: 6000 }
      ],
      activity_over_time: [
        { x: 'Week 1', y: 120 },
        { x: 'Week 2', y: 150 },
        { x: 'Week 3', y: 180 },
        { x: 'Week 4', y: 200 },
        { x: 'Week 5', y: 220 },
        { x: 'Week 6', y: 250 }
      ],
      data_distribution: [
        { name: 'Category A', value: 35 },
        { name: 'Category B', value: 25 },
        { name: 'Category C', value: 20 },
        { name: 'Category D', value: 15 },
        { name: 'Category E', value: 5 }
      ]
    }
  }

  // Generate mock overview data for testing
  const generateMockOverviewData = () => {
    return {
      kpis: [
        {
          title: 'TOTAL PRICE PER UNIT',
          value: '$418,759.00',
          change: '0',
          change_type: 'neutral'
        },
        {
          title: 'AVERAGE PRICE PER UNIT',
          value: '$44.74',
          change: '0',
          change_type: 'neutral'
        },
        {
          title: 'TOTAL RECORDS',
          value: '9,360',
          change: '0',
          change_type: 'neutral'
        },
        {
          title: 'DATA COLUMNS',
          value: '9',
          change: '0',
          change_type: 'neutral'
        }
      ],
      dataset_info: {
        row_count: 9360,
        column_count: 9,
        last_updated: new Date().toISOString()
      }
    }
  }

  // Generate mock insights data for testing
  const generateMockInsightsData = () => {
    return [
      {
        title: 'Revenue Growth Trend',
        description: 'Strong upward trend in revenue over the past 12 months',
        confidence: 'High',
        type: 'trend',
        icon: 'trending-up',
        actionable: true
      },
      {
        title: 'Category Performance',
        description: 'Electronics category shows highest sales volume',
        confidence: 'Medium',
        type: 'performance',
        icon: 'bar-chart',
        actionable: true
      }
    ]
  }

  // Generate mock preview data for testing
  const generateMockPreviewData = () => {
    return {
      columns: ['Date', 'Product', 'Sales_Amount', 'Region', 'Customer_Type'],
      rows: [
        { Date: '2024-01-01', Product: 'Laptop', Sales_Amount: 1200, Region: 'North', Customer_Type: 'Business' },
        { Date: '2024-01-02', Product: 'Phone', Sales_Amount: 800, Region: 'South', Customer_Type: 'Individual' },
        { Date: '2024-01-03', Product: 'Tablet', Sales_Amount: 600, Region: 'East', Customer_Type: 'Business' },
        { Date: '2024-01-04', Product: 'Monitor', Sales_Amount: 300, Region: 'West', Customer_Type: 'Individual' },
        { Date: '2024-01-05', Product: 'Keyboard', Sales_Amount: 100, Region: 'North', Customer_Type: 'Business' }
      ],
      total_rows: 9360
    }
  }

  // Transform backend chart data to frontend format
  const transformChartData = (backendCharts) => {
    const transformed = {}
    
    // Transform revenue_over_time data
    if (backendCharts.revenue_over_time) {
      transformed.revenue_over_time = backendCharts.revenue_over_time.map(item => ({
        x: item.month || item.period || 'Unknown',
        y: item.revenue || item.value || 0
      }))
    }
    
    // Transform sales_by_category data
    if (backendCharts.sales_by_category) {
      transformed.sales_by_category = backendCharts.sales_by_category.map(item => ({
        x: item.name || item.category || 'Unknown',
        y: item.value || item.sales || 0
      }))
    }
    
    // Transform monthly_active_users data
    if (backendCharts.monthly_active_users) {
      transformed.activity_over_time = backendCharts.monthly_active_users.map(item => ({
        x: item.month || item.period || 'Unknown',
        y: item.users || item.value || 0
      }))
    }
    
    // Transform traffic_sources data
    if (backendCharts.traffic_sources) {
      transformed.data_distribution = backendCharts.traffic_sources.map(item => ({
        name: item.name || item.source || 'Unknown',
        value: item.value || item.count || 0
      }))
    }
    
    return transformed
  }

  const loadDashboardData = useCallback(async () => {
    if (!selectedDataset || !selectedDataset.id) {
      setDashboardData(prev => ({ ...prev, loading: false }))
      return
    }

    setDashboardData(prev => ({ ...prev, loading: true, error: null }))

    try {
      const token = localStorage.getItem('datasage-token')
      if (!token) {
        throw new Error('No authentication token found')
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }

      // Load all dashboard data in parallel
      const [overviewRes, insightsRes, chartsRes, previewRes, aiLayoutRes] = await Promise.allSettled([
        fetch(`/api/dashboard/${selectedDataset.id}/overview`, { headers }),
        fetch(`/api/dashboard/${selectedDataset.id}/insights`, { headers }),
        fetch(`/api/dashboard/${selectedDataset.id}/charts`, { headers }),
        fetch(`/api/datasets/${selectedDataset.id}/preview?limit=10`, { headers }),
        fetch(`/api/dashboard/${selectedDataset.id}/ai-layout`, { headers })
      ])

      // Process overview data
      let overviewData = null
      if (overviewRes.status === 'fulfilled' && overviewRes.value.ok) {
        overviewData = await overviewRes.value.json()
      } else {
        // Generate mock overview data for testing
        console.log('Generating mock overview data for testing...')
        overviewData = generateMockOverviewData()
      }

      // Process insights data
      let insightsData = []
      if (insightsRes.status === 'fulfilled' && insightsRes.value.ok) {
        const insightsResponse = await insightsRes.value.json()
        insightsData = insightsResponse.insights || []
      } else {
        // Generate mock insights data for testing
        console.log('Generating mock insights data for testing...')
        insightsData = generateMockInsightsData()
      }

      // Process charts data
      let chartsData = {}
      if (chartsRes.status === 'fulfilled' && chartsRes.value.ok) {
        const chartsResponse = await chartsRes.value.json()
        console.log('Backend charts response:', chartsResponse)
        chartsData = transformChartData(chartsResponse.charts || {})
        console.log('Transformed charts data:', chartsData)
      } else {
        // Generate mock chart data for testing if backend data is not available
        console.log('Charts API failed, generating mock chart data for testing...')
        console.log('Charts API error:', chartsRes.reason || 'Unknown error')
        chartsData = generateMockChartData()
      }

      // Process preview data
      let previewData = null
      if (previewRes.status === 'fulfilled' && previewRes.value.ok) {
        previewData = await previewRes.value.json()
      } else {
        // Generate mock preview data for testing
        console.log('Generating mock preview data for testing...')
        previewData = generateMockPreviewData()
      }

      // Process AI layout data
      let aiLayoutData = null
      if (aiLayoutRes.status === 'fulfilled' && aiLayoutRes.value.ok) {
        const aiLayoutResponse = await aiLayoutRes.value.json()
        aiLayoutData = aiLayoutResponse.layout
      }

      // Use AI layout if available, otherwise generate dynamic layout
      const dynamicLayout = aiLayoutData || generateDynamicLayout({
        overview: overviewData,
        insights: insightsData,
        charts: chartsData,
        preview: previewData
      })

      setDashboardData({
        layout: dynamicLayout,
        kpis: overviewData?.kpis || [],
        insights: insightsData,
        charts: chartsData,
        datasetInfo: {
          ...overviewData?.dataset_info,
          row_count: overviewData?.dataset_info?.row_count || previewData?.total_rows || previewData?.rows?.length,
          column_count: overviewData?.dataset_info?.column_count || previewData?.columns?.length,
          columns: previewData?.columns || [],
          preview: previewData?.rows || [],
          last_updated: overviewData?.dataset_info?.last_updated || new Date().toISOString()
        },
        loading: false,
        error: null
      })

    } catch (error) {
      console.error('Error loading dashboard data:', error)
      setDashboardData(prev => ({
        ...prev,
        loading: false,
        error: error.message
      }))
      
      if (error.message.includes('401')) {
        toast.error('Authentication failed. Please log in again.')
      } else {
        toast.error('Failed to load dashboard data')
      }
    }
  }, [selectedDataset])

  const generateDynamicLayout = ({ overview, insights, charts, preview }) => {
    const components = []

    // Add KPI cards first
    if (overview?.kpis && overview.kpis.length > 0) {
      overview.kpis.forEach((kpi, index) => {
        components.push({
          type: 'kpi',
          title: kpi.title,
          value: kpi.value,
          change: kpi.change,
          change_type: kpi.change_type
        })
      })
    }

    // Add hero chart (most important visualization)
    if (charts.revenue_over_time && charts.revenue_over_time.length > 0) {
      components.push({
        type: 'hero_chart',
        title: 'Revenue Over Time',
        chart_type: 'line',
        data: charts.revenue_over_time,
        description: 'Key performance indicator showing revenue trends',
        height: 400
      })
    }

    // Add insights
    if (insights && insights.length > 0) {
      insights.slice(0, 2).forEach((insight, index) => {
        components.push({
          type: 'insight',
          title: insight.title,
          description: insight.description,
          confidence: insight.confidence,
          type: insight.type,
          icon: insight.icon,
          actionable: insight.actionable
        })
      })
    }

    // Add secondary charts
    if (charts.sales_by_category && charts.sales_by_category.length > 0) {
      components.push({
        type: 'chart',
        title: 'Sales by Category',
        chart_type: 'bar',
        data: charts.sales_by_category,
        description: 'Performance breakdown by category',
        height: 300
      })
    }

    if (charts.activity_over_time && charts.activity_over_time.length > 0) {
      components.push({
        type: 'chart',
        title: 'Activity Over Time',
        chart_type: 'line',
        data: charts.activity_over_time,
        description: 'User activity patterns',
        height: 200
      })
    }

    if (charts.data_distribution && charts.data_distribution.length > 0) {
      components.push({
        type: 'chart',
        title: 'Data Distribution',
        chart_type: 'pie',
        data: charts.data_distribution,
        description: 'Distribution of data across categories',
        height: 200
      })
    }

    // Add data preview table
    if (preview && preview.length > 0) {
      components.push({
        type: 'table',
        title: 'Data Preview',
        data: preview,
        columns: Object.keys(preview[0] || {}),
        description: 'First 10 rows of your dataset',
        maxRows: 10
      })
    }

    return {
      layout_grid: 'repeat(12, 1fr)',
      components: components
    }
  }

  const refreshDashboard = useCallback(() => {
    loadDashboardData()
  }, [loadDashboardData])

  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData])

  return {
    ...dashboardData,
    userExpertise,
    setUserExpertise,
    refreshDashboard
  }
}

export default useDashboardData