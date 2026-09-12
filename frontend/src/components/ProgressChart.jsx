import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDate } from './ui'

/**
 * Score of each completed interview over time.
 *
 * Lazy-loaded from the dashboard: the charting library is larger than the rest
 * of the app put together, and every other page manages without it.
 */
export default function ProgressChart({ points }) {
  const data = points.map((point, index) => ({
    ...point,
    label: `#${index + 1}`,
    date: formatDate(point.completed_at),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#efe4db" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: '#8d7b68' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 10]}
          ticks={[0, 2, 4, 6, 8, 10]}
          tick={{ fontSize: 12, fill: '#8d7b68' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value) => [`${value}/10`, 'Score']}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
          contentStyle={{
            fontSize: 12,
            borderRadius: 16,
            border: '1px solid #f0e5dc',
            boxShadow: '0 14px 40px -14px rgba(120, 60, 25, 0.25)',
          }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#ef6f4f"
          strokeWidth={2.5}
          dot={{ r: 3, fill: '#ef6f4f', strokeWidth: 0 }}
          activeDot={{ r: 5, fill: '#ef6f4f' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
