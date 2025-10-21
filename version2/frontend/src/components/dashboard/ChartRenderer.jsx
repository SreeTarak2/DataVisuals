import React from 'react'
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  BarChart, Bar, PieChart, Pie, Cell, ScatterChart, Scatter 
} from 'recharts'
import { TrendingUp, BarChart3, PieChart as PieIcon, ScatterChart as ScatterIcon } from 'lucide-react'

const ChartRenderer = ({ 
  title, 
  chart_type, 
  data, 
  description, 
  height = 300,
  showDataPoints = true 
}) => {
  const getChartIcon = () => {
    switch (chart_type) {
      case 'line':
        return <TrendingUp className="w-5 h-5 text-blue-400" />
      case 'bar':
        return <BarChart3 className="w-5 h-5 text-green-400" />
      case 'pie':
        return <PieIcon className="w-5 h-5 text-purple-400" />
      case 'scatter':
        return <ScatterIcon className="w-5 h-5 text-orange-400" />
      default:
        return <BarChart3 className="w-5 h-5 text-blue-400" />
    }
  }

  const renderChart = () => {
    if (!data || data.length === 0) {
      return (
        <div className="flex items-center justify-center h-48">
          <div className="text-center">
            <div className="w-16 h-16 bg-slate-800/50 rounded-2xl flex items-center justify-center mx-auto mb-4">
              {getChartIcon()}
            </div>
            <p className="text-slate-500 text-sm">Chart will appear when data is available</p>
          </div>
        </div>
      )
    }

    const commonProps = {
      width: "100%",
      height: height,
      data: data
    }

    switch (chart_type) {
      case 'line':
        return (
          <ResponsiveContainer {...commonProps}>
            <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="1 1" stroke="#334155" opacity={0.2} />
              <XAxis 
                dataKey="x" 
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
              />
              <YAxis 
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
                tickFormatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#f1f5f9',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                }}
                formatter={(value, name) => [typeof value === 'number' ? value.toLocaleString() : value, name]}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Line 
                type="monotone" 
                dataKey="y" 
                stroke="#3b82f6" 
                strokeWidth={2}
                dot={showDataPoints ? { fill: '#3b82f6', strokeWidth: 2, r: 4 } : false}
                activeDot={{ r: 6, stroke: '#3b82f6', strokeWidth: 2, fill: '#1d4ed8' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )

      case 'bar':
        return (
          <ResponsiveContainer {...commonProps}>
            <BarChart data={data} margin={{ top: 15, right: 20, left: 15, bottom: 35 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
              <XAxis 
                dataKey="x" 
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
                angle={-45}
                textAnchor="end"
                height={20}
              />
              <YAxis 
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
                tickFormatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'black',
                  border: '1px solid #334155',
                  borderRadius: '15px',
                  color: '#f1f5f9',
                  boxShadow: '0 10px 25px rgba(0, 0, 0, 0.47)'
                }}
                formatter={(value, name) => [typeof value === 'number' ? value.toLocaleString() : value, name]}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Bar 
                dataKey="y" 
                fill="#3b82f6" 
                radius={[5, 5, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )

      case 'pie':
        const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
        return (
          <ResponsiveContainer {...commonProps}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#f1f5f9'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        )

      case 'scatter':
        return (
          <ResponsiveContainer {...commonProps}>
            <ScatterChart data={data} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
              <XAxis 
                dataKey="x" 
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
              />
              <YAxis 
                dataKey="y" 
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#94a3b8' }}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#f1f5f9'
                }}
              />
              <Scatter dataKey="y" fill="#f59e0b" />
            </ScatterChart>
          </ResponsiveContainer>
        )

      default:
        return (
          <div className="flex items-center justify-center h-48 text-slate-400">
            <p>Unsupported chart type: {chart_type}</p>
          </div>
        )
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
          {description && (
            <p className="text-slate-400 text-sm">{description}</p>
          )}
        </div>
        <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
          {getChartIcon()}
        </div>
      </div>
      
      <div className="flex-1">
        {renderChart()}
      </div>
    </div>
  )
}

export default ChartRenderer

